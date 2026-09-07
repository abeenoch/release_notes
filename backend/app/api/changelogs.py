from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.core.dependencies import get_db, get_current_user_id
from app.core.security import encrypt_api_key
from app.models.user import User
from app.models.repo import Repository
from app.models.user_config import UserLlmConfig
from app.models.changelog import Changelog as ChangelogModel
from app.schemas.changelog import (
    LlmConfigCreate, LlmConfigResponse,
    ChangelogTriggerRequest, ChangelogResponse, ChangelogListResponse,
)
from app.services.changelog_service import ChangelogService
from app.services import publish_service
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
    return LlmConfigResponse(
        id=config.id, provider=config.provider, model=config.model,
        base_url=config.base_url, is_active=True,
        has_api_key=True, created_at=config.created_at,
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

# ── Publishing: GitHub Release + CHANGELOG.md commit ──


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
    """Create a GitHub Release on the changelog's tag with the generated notes."""
    changelog, repo = await _load_changelog_and_repo(changelog_id, user_id, db)
    try:
        result = await publish_service.publish_release(changelog, repo, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:  # GitHub API errors → 502 with detail
        logger.exception("Release publish failed for changelog %s", changelog_id)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)[:500])
    return result


@router.post("/{changelog_id}/commit-changelog")
async def commit_changelog_file(
    changelog_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Create or update CHANGELOG.md in the target repository."""
    changelog, repo = await _load_changelog_and_repo(changelog_id, user_id, db)
    try:
        result = await publish_service.commit_changelog_file(changelog, repo, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.exception("CHANGELOG.md commit failed for changelog %s", changelog_id)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)[:500])
    return result

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
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    query = select(ChangelogModel).where(ChangelogModel.user_id == user_id)
    if repo_id:
        query = query.where(ChangelogModel.repo_id == repo_id)
    query = query.order_by(ChangelogModel.created_at.desc()).limit(50)
    result = await db.execute(query)
    changelogs = result.scalars().all()
    return ChangelogListResponse(changelogs=[
        ChangelogResponse(
            id=c.id, repo_id=c.repo_id,
            from_tag=c.from_tag, to_tag=c.to_tag,
            version=c.version, previous_version=c.previous_version,
            summary=c.summary, raw_markdown=c.raw_markdown,
            llm_provider=c.llm_provider, commit_count=c.commit_count,
            status=c.status, error_message=c.error_message,
            notification_status=c.notification_status,
            created_at=c.created_at,
        )
        for c in changelogs
    ])


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
        created_at=changelog.created_at,
    )
    await db.delete(config)