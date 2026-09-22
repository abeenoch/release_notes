"""Tests for the notify-config DELETE fix — it previously 204'd without
deleting anything (same bug as LLM configs in a57d749)."""
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.notify_routes import delete_notify_config
from app.database import Base
from app.models.notify_config import UserNotifyConfig
from app.models.user import User


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite://", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_delete_notify_config_removes_row(db):
    user = User(github_id="9", github_login="deleter")
    db.add(user)
    await db.flush()
    cfg = UserNotifyConfig(user_id=user.id, provider="slack", slack_webhook_url="https://x")
    db.add(cfg)
    await db.commit()

    await delete_notify_config(config_id=cfg.id, user_id=user.id, db=db)
    await db.commit()

    remaining = (await db.execute(select(UserNotifyConfig))).scalars().all()
    assert remaining == []


@pytest.mark.asyncio
async def test_delete_notify_config_404(db):
    from fastapi import HTTPException
    user = User(github_id="10", github_login="ghost")
    db.add(user)
    await db.commit()
    with pytest.raises(HTTPException) as exc:
        await delete_notify_config(config_id="missing", user_id=user.id, db=db)
    assert exc.value.status_code == 404
