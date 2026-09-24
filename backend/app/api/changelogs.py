from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.core.dependencies import get_db, get_current_user_id
from app.core.security import encrypt_api_key
from app.models.user import User
from app.models.repo import Repository
from app.models.user_config import UserLlmConfig
from app.models.changelog import Changelog as ChangelogModel
from app.schemas.changelog import (
    LlmConfigCreate, LlmConfigResponse, LlmConfigUpdate,
    ChangelogTriggerRequest, ChangelogResponse, ChangelogListResponse,
    ChangelogStatsResponse,
)
from app.services.changelog_service import ChangelogService, repo_work_dir
from app.services.git_ops import ref_exists, validate_ref_shape
from app.services import publish_service
from app.services.github import GitHubApiError
from app.tasks.worker import run_changelog_generation
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/changelogs", tags=["changelogs"])

# ── LLM Config ──


@router.get("/configs", response_model=list[LlmConfigResponse])
async def list_llm_configs(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserLlmConfig).where(UserLlmConfig.user_id == user_id)
    )
    configs = result.scalars().all()
    return [
        LlmConfigResponse(
            id=c.id, provider=c.provider, model=c.model,
            base_url=c.base_url, is_active=c.is_active,
            has_api_key=bool(c.api_key_encrypted), created_at=c.created_at,
        )
        for c in configs
    ]
@router.post("/configs", response_model=LlmConfigResponse)
async def create_llm_config(
    body: LlmConfigCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    if body.provider == "commit":
        config = UserLlmConfig(user_id=user_id, provider="commit", is_active=True)
        db.add(config)
        await db.flush()
        await db.commit()
        return LlmConfigResponse(
            id=config.id, provider="commit", is_active=True,
            has_api_key=False, created_at=config.created_at,
        )
    if not body.api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key is required for this provider",
        )
    # Deactivate all other configs, then create a new active one
    existing = await db.execute(
        select(UserLlmConfig).where(
            UserLlmConfig.user_id == user_id,
            UserLlmConfig.is_active == True,
        )
    )
    for cfg in existing.scalars().all():
        cfg.is_active = False
    config = UserLlmConfig(
        user_id=user_id, provider=body.provider,
        api_key_encrypted=encrypt_api_key(body.api_key),
        model=body.model, base_url=body.base_url, is_active=True,
    )
    db.add(config)
    await db.flush()
    await db.commit()
    return LlmConfigResponse(
        id=config.id, provider=config.provider, model=config.model,
        base_url=config.base_url, is_active=True,
        has_api_key=True, created_at=config.created_at,
    )


@router.patch("/configs/{config_id}", response_model=LlmConfigResponse)
async def update_llm_config(
    config_id: str,
    body: LlmConfigUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserLlmConfig).where(
            UserLlmConfig.id == config_id,
            UserLlmConfig.user_id == user_id,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")

    # When activating this config, deactivate all the others for this user
    if body.is_active is True and not config.is_active:
        others = await db.execute(
            select(UserLlmConfig).where(
                UserLlmConfig.user_id == user_id,
                UserLlmConfig.id != config_id,
                UserLlmConfig.is_active == True,
            )
        )
        for other in others.scalars().all():
            other.is_active = False

    if body.api_key is not None:
        if body.api_key == "":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot clear an API key — send the new key to replace it",
            )
        config.api_key_encrypted = encrypt_api_key(body.api_key)
    if body.model is not None:
        config.model = body.model or None
    if body.base_url is not None:
        config.base_url = body.base_url or None
    if body.is_active is not None:
        config.is_active = body.is_active

    await db.flush()
    await db.refresh(config)
    await db.commit()
    return LlmConfigResponse(
        id=config.id, provider=config.provider, model=config.model,
        base_url=config.base_url, is_active=config.is_active,
        has_api_key=bool(config.api_key_encrypted), created_at=config.created_at,
    )


@router.delete("/configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_config(
    config_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserLlmConfig).where(
            UserLlmConfig.id == config_id,
            UserLlmConfig.user_id == user_id,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")
    await db.delete(config)
    await db.commit()
    return None

# ── Publishing: GitHub Release ──


async def _load_changelog_and_repo(
    changelog_id: str, user_id: str, db: AsyncSession
) -> tuple[ChangelogModel, Repository]:
    result = await db.execute(
        select(ChangelogModel).where(
            ChangelogModel.id == changelog_id,
            ChangelogModel.user_id == user_id,
        )
    )
    changelog = result.scalar_one_or_none()
    if not changelog:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Changelog not found")
    if changelog.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only completed changelogs can be published",
        )
    repo = await db.get(Repository, changelog.repo_id)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    return changelog, repo


@router.post("/{changelog_id}/publish-release")
async def publish_github_release(
    changelog_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Publish the changelog's notes as a GitHub Release.

    Idempotent: if this changelog (or its tag) already has a release, responds
    200 with status "already_published" instead of updating or erroring.
    """
    changelog, repo = await _load_changelog_and_repo(changelog_id, user_id, db)
    try:
        return await publish_service.publish_release(changelog, repo, db)
    except ValueError as exc:
        # Bad input on our side (e.g. no tag to release) → 400.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except GitHubApiError as exc:
        # GitHub said no — surface its status honestly instead of a blanket 502.
        logger.warning(
            "GitHub rejected release publish for changelog %s: HTTP %s",
            changelog_id, exc.status_code,
        )
        http_status = (
            status.HTTP_404_NOT_FOUND if exc.status_code == 404
            else status.HTTP_403_FORBIDDEN if exc.status_code in (401, 403)
            else status.HTTP_429_TOO_MANY_REQUESTS if exc.status_code == 429
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(status_code=http_status, detail=exc.detail)
    except Exception:
        logger.exception("Release publish failed for changelog %s", changelog_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Publishing to GitHub failed — please try again",
        )


# ── Changelog Generation ──


@router.post("/generate", status_code=status.HTTP_202_ACCEPTED, response_model=ChangelogResponse)
async def generate_changelog(
    body: ChangelogTriggerRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Enqueue a changelog generation task. Returns immediately with a pending record."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    result = await db.execute(
        select(Repository).where(
            Repository.id == body.repo_id,
            Repository.user_id == user_id,
        )
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    # ── Manual range validation (fail before anything is queued) ──
    if body.from_tag or body.to_tag:
        if not (body.from_tag and body.to_tag):
            # Partial ranges were previously *silently ignored* by the service
            # (it only honors an explicit range when both ends are given) —
            # now they're a clear 400 instead of a wrong changelog.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide both from_tag and to_tag, or neither "
                       "(omit both for the default incremental range)",
            )
        for label, ref in (("from_tag", body.from_tag), ("to_tag", body.to_tag)):
            err = validate_ref_shape(ref)
            if err:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid {label}: {err}",
                )
        # If the repo is already cloned, verify the refs actually exist here
        # so a typo 400s immediately. No clone yet → skip: the worker will
        # report an unknown ref as a normal (visible) generation failure.
        work_dir = repo_work_dir(user.id, repo)
        if (work_dir / ".git").exists():
            missing = [
                r for r in (body.from_tag, body.to_tag)
                if not ref_exists(work_dir, r)
            ]
            if missing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unknown ref(s) in this repository: {', '.join(missing)}",
                )

    # Create a pending record so the frontend can immediately show it
    changelog = ChangelogModel(
        user_id=user.id,
        repo_id=repo.id,
        from_tag=body.from_tag,
        to_tag=body.to_tag,
        status="pending",
    )
    db.add(changelog)
    await db.flush()
    await db.refresh(changelog)

    # Commit explicitly so the background task (which uses its own session)
    # can see this row — otherwise it opens a fresh session, finds nothing,
    # and the changelog is left stuck in "pending". (Same pattern as webhooks.)
    await db.commit()

    # Enqueue the background task
    background_tasks.add_task(run_changelog_generation, changelog.id)

    return ChangelogResponse(
        id=changelog.id, repo_id=changelog.repo_id,
        from_tag=changelog.from_tag, to_tag=changelog.to_tag,
        status="pending", created_at=changelog.created_at,
    )


@router.get("/", response_model=ChangelogListResponse)
async def list_changelogs(
    repo_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    query = select(ChangelogModel).where(ChangelogModel.user_id == user_id)
    if repo_id:
        query = query.where(ChangelogModel.repo_id == repo_id)
    query = query.order_by(ChangelogModel.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    changelogs = result.scalars().all()
    count_q = select(func.count()).select_from(ChangelogModel).where(
        ChangelogModel.user_id == user_id
    )
    if repo_id:
        count_q = count_q.where(ChangelogModel.repo_id == repo_id)
    total = (await db.execute(count_q)).scalar_one()
    return ChangelogListResponse(changelogs=[
        ChangelogResponse(
            id=c.id, repo_id=c.repo_id,
            from_tag=c.from_tag, to_tag=c.to_tag,
            version=c.version, previous_version=c.previous_version,
            summary=c.summary, raw_markdown=c.raw_markdown,
            llm_provider=c.llm_provider, commit_count=c.commit_count,
            status=c.status, error_message=c.error_message,
            notification_status=c.notification_status,
            release_url=c.release_url, published_at=c.published_at,
            created_at=c.created_at,
        )
        for c in changelogs
    ], total=total)


@router.get("/stats/summary", response_model=ChangelogStatsResponse)
async def changelog_stats(
    repo_id: str | None = None,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Dashboard counts. Full totals — never the length of a paginated page."""
    base = [ChangelogModel.user_id == user_id]
    if repo_id:
        base.append(ChangelogModel.repo_id == repo_id)
    total = (await db.execute(
        select(func.count()).select_from(ChangelogModel).where(*base)
    )).scalar_one()
    completed = (await db.execute(
        select(func.count()).select_from(ChangelogModel).where(*base, ChangelogModel.status == "completed")
    )).scalar_one()
    failed = (await db.execute(
        select(func.count()).select_from(ChangelogModel).where(*base, ChangelogModel.status == "failed")
    )).scalar_one()
    published = (await db.execute(
        select(func.count()).select_from(ChangelogModel).where(*base, ChangelogModel.release_url.is_not(None))
    )).scalar_one()
    return ChangelogStatsResponse(
        changelogs_total=total,
        changelogs_completed=completed,
        changelogs_failed=failed,
        changelogs_published=published,
    )


@router.get("/{changelog_id}", response_model=ChangelogResponse)
async def get_changelog(
    changelog_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChangelogModel).where(
            ChangelogModel.id == changelog_id,
            ChangelogModel.user_id == user_id,
        )
    )
    changelog = result.scalar_one_or_none()
    if not changelog:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Changelog not found")
    return ChangelogResponse(
        id=changelog.id, repo_id=changelog.repo_id,
        from_tag=changelog.from_tag, to_tag=changelog.to_tag,
        version=changelog.version, previous_version=changelog.previous_version,
        summary=changelog.summary, raw_markdown=changelog.raw_markdown,
        llm_provider=changelog.llm_provider, commit_count=changelog.commit_count,
        status=changelog.status, error_message=changelog.error_message,
        notification_status=changelog.notification_status,
        release_url=changelog.release_url, published_at=changelog.published_at,
        created_at=changelog.created_at,
    )