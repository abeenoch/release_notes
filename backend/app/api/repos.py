from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_db, get_current_user_id
from app.core.security import decrypt_api_key
from app.models.user import User
from app.models.repo import Repository
from app.schemas.repo import (
    RepoCreate, RepoResponse, RepoListResponse,
    RepoToggleActive, GitHubRepoPreview, GitHubRepoListResponse,
    RepoImportRequest,
)
from app.services.github import GitHubClient
from app.config import settings

router = APIRouter(prefix="/repos", tags=["repos"])


@router.get("/", response_model=RepoListResponse)
async def list_repos(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List only the repos the user has actively added/imported."""
    result = await db.execute(
        select(Repository).where(Repository.user_id == user_id).order_by(Repository.full_name)
    )
    repos = result.scalars().all()
    return RepoListResponse(repos=[
        RepoResponse(
            id=r.id,
            full_name=r.full_name,
            default_branch=r.default_branch,
            is_active=r.is_active,
            is_private=r.is_private,
            created_at=r.created_at,
        )
        for r in repos
    ])


@router.post("/preview", response_model=GitHubRepoListResponse)
async def preview_github_repos(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Fetch ALL repos from GitHub for preview/selection (no DB save)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.github_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub not connected.",
        )

    gh_token = decrypt_api_key(user.github_token)
    gh = GitHubClient(
        client_id=settings.github_client_id or "",
        client_secret=settings.github_client_secret or "",
    )
    gh_repos = await gh.get_user_repos(gh_token)

    existing = await db.execute(
        select(Repository.full_name).where(Repository.user_id == user_id)
    )
    existing_names = {row[0] for row in existing.fetchall()}

    repos = []
    for gh_repo in gh_repos:
        full_name = gh_repo["full_name"]
        repos.append(GitHubRepoPreview(
            full_name=full_name,
            default_branch=gh_repo.get("default_branch", "main"),
            is_private=gh_repo.get("private", False),
            description=gh_repo.get("description"),
            already_added=full_name in existing_names,
        ))

    return GitHubRepoListResponse(repos=repos)


@router.post("/sync", response_model=RepoListResponse)
async def sync_github_repos(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Fetch repos from GitHub and save ALL to DB (inactive by default)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.github_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub not connected.",
        )

    gh_token = decrypt_api_key(user.github_token)
    gh = GitHubClient(
        client_id=settings.github_client_id or "",
        client_secret=settings.github_client_secret or "",
    )
    gh_repos = await gh.get_user_repos(gh_token)

    synced = []
    for gh_repo in gh_repos:
        full_name = gh_repo["full_name"]
        existing = await db.execute(
            select(Repository).where(
                Repository.user_id == user_id,
                Repository.full_name == full_name,
            )
        )
        repo = existing.scalar_one_or_none()
        if repo:
            repo.clone_url = gh_repo.get("clone_url", repo.clone_url)
            repo.default_branch = gh_repo.get("default_branch", repo.default_branch)
            repo.is_private = gh_repo.get("private", repo.is_private)
            # Keep existing is_active
        else:
            repo = Repository(
                user_id=user_id,
                github_repo_id=gh_repo["id"],
                full_name=full_name,
                clone_url=gh_repo.get("clone_url"),
                default_branch=gh_repo.get("default_branch", "main"),
                is_private=gh_repo.get("private", False),
                is_active=False,
            )
            db.add(repo)
        synced.append(repo)

    await db.flush()
    return RepoListResponse(repos=[
        RepoResponse(
            id=r.id,
            full_name=r.full_name,
            default_branch=r.default_branch,
            is_active=r.is_active,
            is_private=r.is_private,
            created_at=r.created_at,
        )
        for r in synced
    ])


@router.post("/import", response_model=RepoListResponse)
async def import_selected_repos(
    body: RepoImportRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Import selected repos from GitHub into the system.
    Only the repos specified in `full_names` will be saved and activated.
    Already-imported repos are re-activated if they were inactive.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.github_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub not connected.",
        )

    gh_token = decrypt_api_key(user.github_token)
    gh = GitHubClient(
        client_id=settings.github_client_id or "",
        client_secret=settings.github_client_secret or "",
    )

    imported: list[Repository] = []
    for full_name in body.full_names:
        # Check if already exists
        existing = await db.execute(
            select(Repository).where(
                Repository.user_id == user_id,
                Repository.full_name == full_name,
            )
        )
        repo = existing.scalar_one_or_none()
        if repo:
            repo.is_active = True
            imported.append(repo)
            continue

        # Fetch repo details from GitHub
        try:
            gh_repo = await gh.get_repo(gh_token, full_name)
        except Exception:
            continue  # Skip repos we can't fetch

        repo = Repository(
            user_id=user_id,
            github_repo_id=gh_repo.get("id"),
            full_name=full_name,
            clone_url=gh_repo.get("clone_url"),
            default_branch=gh_repo.get("default_branch", "main"),
            is_private=gh_repo.get("private", False),
            is_active=True,
        )
        db.add(repo)
        imported.append(repo)

    await db.flush()
    return RepoListResponse(repos=[
        RepoResponse(
            id=r.id,
            full_name=r.full_name,
            default_branch=r.default_branch,
            is_active=r.is_active,
            is_private=r.is_private,
            created_at=r.created_at,
        )
        for r in imported
    ])


@router.patch("/{repo_id}/toggle", response_model=RepoResponse)
async def toggle_repo_active(
    repo_id: str,
    body: RepoToggleActive | None = None,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Toggle or set a repository's active state.
    
    If body.is_active is provided, set it to that value.
    Otherwise, toggle the current state.
    """
    result = await db.execute(
        select(Repository).where(
            Repository.id == repo_id,
            Repository.user_id == user_id,
        )
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    
    if body is not None and body.is_active is not None:
        repo.is_active = body.is_active
    else:
        repo.is_active = not repo.is_active
    
    await db.flush()
    return RepoResponse(
        id=repo.id,
        full_name=repo.full_name,
        default_branch=repo.default_branch,
        is_active=repo.is_active,
        is_private=repo.is_private,
        created_at=repo.created_at,
    )


@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_repo(
    repo_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Remove a connected repository."""
    result = await db.execute(
        select(Repository).where(
            Repository.id == repo_id,
            Repository.user_id == user_id,
        )
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    await db.delete(repo)