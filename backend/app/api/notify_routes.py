from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_db, get_current_user_id
from app.core.security import encrypt_api_key
from app.models.notify_config import UserNotifyConfig
from app.schemas.notify import (
    NotifyConfigCreate,
    NotifyConfigResponse,
    NotifyConfigListResponse,
)

router = APIRouter(prefix="/notify", tags=["notify"])


@router.get("/configs", response_model=NotifyConfigListResponse)
async def list_notify_configs(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserNotifyConfig).where(UserNotifyConfig.user_id == user_id)
    )
    configs = result.scalars().all()
    return NotifyConfigListResponse(configs=[
        NotifyConfigResponse(
            id=c.id,
            provider=c.provider,
            smtp_host=c.smtp_host,
            smtp_port=c.smtp_port,
            smtp_user=c.smtp_user,
            has_smtp_pass=bool(c.smtp_pass_encrypted),
            smtp_secure=c.smtp_secure,
            has_sendgrid_key=bool(c.sendgrid_api_key_encrypted),
            slack_webhook_url=c.slack_webhook_url,
            slack_channel=c.slack_channel,
            from_email=c.from_email,
            to_email=c.to_email,
            subject_prefix=c.subject_prefix,
            is_active=c.is_active,
            created_at=c.created_at,
        )
        for c in configs
    ])


@router.post("/configs", response_model=NotifyConfigResponse)
async def create_notify_config(
    body: NotifyConfigCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    # Deactivate all other configs
    existing = await db.execute(
        select(UserNotifyConfig).where(
            UserNotifyConfig.user_id == user_id,
            UserNotifyConfig.is_active == True,
        )
    )
    for cfg in existing.scalars().all():
        cfg.is_active = False

    config = UserNotifyConfig(
        user_id=user_id,
        provider=body.provider,
        smtp_host=body.smtp_host,
        smtp_port=body.smtp_port,
        smtp_user=body.smtp_user,
        smtp_pass_encrypted=encrypt_api_key(body.smtp_pass) if body.smtp_pass else None,
        smtp_secure=body.smtp_secure,
        sendgrid_api_key_encrypted=encrypt_api_key(body.sendgrid_api_key) if body.sendgrid_api_key else None,
        slack_webhook_url=body.slack_webhook_url,
        slack_channel=body.slack_channel,
        from_email=body.from_email,
        to_email=body.to_email,
        subject_prefix=body.subject_prefix,
        is_active=True,
    )
    db.add(config)
    await db.flush()

    return NotifyConfigResponse(
        id=config.id,
        provider=config.provider,
        smtp_host=config.smtp_host,
        smtp_port=config.smtp_port,
        smtp_user=config.smtp_user,
        has_smtp_pass=bool(config.smtp_pass_encrypted),
        smtp_secure=config.smtp_secure,
        has_sendgrid_key=bool(config.sendgrid_api_key_encrypted),
        slack_webhook_url=config.slack_webhook_url,
        slack_channel=config.slack_channel,
        from_email=config.from_email,
        to_email=config.to_email,
        subject_prefix=config.subject_prefix,
        is_active=True,
        created_at=config.created_at,
    )


@router.delete("/configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notify_config(
    config_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserNotifyConfig).where(
            UserNotifyConfig.id == config_id,
            UserNotifyConfig.user_id == user_id,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")
    await db.delete(config)