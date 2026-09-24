from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.models.changelog import Changelog as ChangelogModel
from app.models.repo import Repository
from app.schemas.changelog import PublicChangelogResponse, PublicPageResponse

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/{owner}/{repo}", response_model=PublicPageResponse)
async def get_public_page(
    owner: str,
    repo: str,
    db: AsyncSession = Depends(get_db),
):
    """Read-only public changelog page for /owner/repo — no auth.

    Serves ONLY opted-in registrations (public_enabled, off by default) and
    only completed changelogs: ids, status, error messages and notification
    state never leave the server. If several users opted in a registration
    of the same name, the active + most recently touched one wins.
    """
    full_name = f"{owner}/{repo}"
    result = await db.execute(
        select(Repository)
        .where(
            Repository.full_name == full_name,
            Repository.public_enabled == True,  # noqa: E712
        )
        .order_by(Repository.is_active.desc(), Repository.updated_at.desc())
    )
    registration = result.scalars().first()
    if not registration:
        # Not registered, not opted in, or private-and-hidden — same 404
        # either way, so the endpoint never confirms existence.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Changelog page not found",
        )

    rows = (await db.execute(
        select(ChangelogModel)
        .where(
            ChangelogModel.repo_id == registration.id,
            ChangelogModel.status == "completed",
        )
        .order_by(ChangelogModel.created_at.desc())
    )).scalars().all()

    return PublicPageResponse(
        full_name=registration.full_name,
        is_private=registration.is_private,
        changelogs=[
            PublicChangelogResponse(
                version=c.version,
                previous_version=c.previous_version,
                from_tag=c.from_tag,
                to_tag=c.to_tag,
                summary=c.summary,
                raw_markdown=c.raw_markdown,
                commit_count=c.commit_count,
                release_url=c.release_url,
                published_at=c.published_at,
                created_at=c.created_at,
            )
            for c in rows
        ],
    )