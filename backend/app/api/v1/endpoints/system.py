from fastapi import APIRouter, Body, HTTPException, Depends
from pydantic import BaseModel
from ....core.config import settings
from ....models.types import GlobalSettings
from ....services.user_manager import UserManager
import requests
from .auth import get_current_user

router = APIRouter()

class SetDefaultUidRequest(BaseModel):
    default_uid: str

class SetPublicUrlRequest(BaseModel):
    public_url: str | None = None

@router.get("/uid")
async def get_default_uid(current_user = Depends(get_current_user)):
    """
    Return the default UID used for agent containers (global setting).
    """
    return {"default_uid": settings.DEFAULT_AGENT_UID}

@router.post("/uid")
async def set_default_uid(
    payload: SetDefaultUidRequest,
    current_user = Depends(get_current_user)
):
    """
    Set the global default UID.
    """
    uid = payload.default_uid
    if uid is not None:
        settings.secrets.set("DEFAULT_AGENT_UID", uid.strip())
        settings.DEFAULT_AGENT_UID = uid.strip()
    return {"status": "ok"}

@router.get("/public-url")
async def get_public_url(current_user = Depends(get_current_user)):
    """Get the currently configured public URL (used for webhooks)."""
    url = settings.secrets.get("PUBLIC_URL")
    return {"public_url": url}

@router.post("/public-url")
async def set_public_url(
    payload: SetPublicUrlRequest,
    current_user = Depends(get_current_user)
):
    """Set the public URL. Pass null or empty string to clear."""
    url = payload.public_url
    if url is not None:
        settings.secrets.set("PUBLIC_URL", url.strip() if url.strip() else None)
    return {"status": "ok"}

@router.get("/detect-public-ip")
async def detect_public_ip(current_user = Depends(get_current_user)):
    """Try to detect the server's public IP using external services."""
    services = ["https://ifconfig.me", "https://icanhazip.com", "https://api.ipify.org"]
    for service in services:
        try:
            resp = requests.get(service, timeout=5)
            if resp.status_code == 200:
                ip = resp.text.strip()
                return {"public_ip": ip}
        except:
            continue
    return {"public_ip": None}

@router.get("/global-settings", response_model=GlobalSettings)
async def get_global_settings(current_user = Depends(get_current_user)):
    """Get all global settings."""
    settings_data = settings.secrets.get("GLOBAL_SETTINGS")
    if settings_data:
        return GlobalSettings(**settings_data)
    return GlobalSettings()

@router.post("/global-settings", response_model=GlobalSettings)
async def set_global_settings(
    payload: GlobalSettings,
    current_user = Depends(get_current_user)
):
    """Update global settings."""
    old_settings_data = settings.secrets.get("GLOBAL_SETTINGS")
    old_enabled = False
    if old_settings_data:
        old_settings = GlobalSettings(**old_settings_data)
        old_enabled = old_settings.login_enabled
    
    if payload.login_enabled and not old_enabled:
        user_manager = UserManager()
        users = await user_manager.list_users()
        admin = next((u for u in users if u.role.value == "GLOBAL_ADMIN"), None)
        if admin and not admin.password_changed:
            raise HTTPException(
                status_code=400,
                detail="Admin must change password before enabling gateway"
            )
    
    settings.secrets.set("GLOBAL_SETTINGS", payload.dict())
    return payload
