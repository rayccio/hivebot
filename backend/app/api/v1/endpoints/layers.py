from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from ....core.database import get_db
from .auth import get_current_user
from ....services.layer_manager import LayerManager

router = APIRouter(prefix="/layers", tags=["layers"])

# --- Response models ---
class LayerResponse(BaseModel):
    id: str
    name: str
    description: str
    version: str
    author: str | None
    dependencies: List[str]
    enabled: bool
    created_at: str
    updated_at: str

class LayerRoleResponse(BaseModel):
    layer_id: str
    role_name: str
    soul_md: str
    identity_md: str
    tools_md: str
    role_type: str
    priority: int

class LayerSkillResponse(BaseModel):
    layer_id: str
    skill_id: str
    skill_name: str
    skill_description: str
    skill_type: str

# --- Request models for Phase 2 ---
class InstallLayerRequest(BaseModel):
    git_url: str
    version: Optional[str] = None

class LayerConfigUpdate(BaseModel):
    config: Dict[str, Any]

class LayerConfigResponse(BaseModel):
    config: Dict[str, Any]

# ----------------------------------------------------------------------
# Existing endpoints (no change)
# ----------------------------------------------------------------------
@router.get("", response_model=List[LayerResponse])
async def list_layers(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    result = await db.execute(
        text("SELECT id, name, description, version, author, dependencies, enabled, created_at, updated_at FROM layers ORDER BY created_at")
    )
    rows = result.fetchall()
    layers = []
    for r in rows:
        layers.append(LayerResponse(
            id=r[0],
            name=r[1],
            description=r[2],
            version=r[3],
            author=r[4],
            dependencies=r[5] or [],
            enabled=r[6],
            created_at=r[7].isoformat(),
            updated_at=r[8].isoformat()
        ))
    return layers

@router.get("/{layer_id}/roles", response_model=List[LayerRoleResponse])
async def list_layer_roles(
    layer_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    result = await db.execute(
        text("SELECT layer_id, role_name, soul_md, identity_md, tools_md, role_type, priority FROM layer_roles WHERE layer_id = :layer_id ORDER BY priority DESC"),
        {"layer_id": layer_id}
    )
    rows = result.fetchall()
    if not rows:
        exists = await db.execute(text("SELECT 1 FROM layers WHERE id = :layer_id"), {"layer_id": layer_id})
        if not exists.fetchone():
            raise HTTPException(status_code=404, detail="Layer not found")
        return []
    roles = []
    for r in rows:
        roles.append(LayerRoleResponse(
            layer_id=r[0],
            role_name=r[1],
            soul_md=r[2],
            identity_md=r[3],
            tools_md=r[4],
            role_type=r[5],
            priority=r[6]
        ))
    return roles

@router.get("/{layer_id}/skills", response_model=List[LayerSkillResponse])
async def list_layer_skills(
    layer_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    result = await db.execute(
        text("""
            SELECT ls.layer_id, s.id, s.data->>'name' as skill_name, s.data->>'description' as skill_description, s.data->>'type' as skill_type
            FROM layer_skills ls
            JOIN skills s ON ls.skill_id = s.id
            WHERE ls.layer_id = :layer_id
        """),
        {"layer_id": layer_id}
    )
    rows = result.fetchall()
    if not rows:
        exists = await db.execute(text("SELECT 1 FROM layers WHERE id = :layer_id"), {"layer_id": layer_id})
        if not exists.fetchone():
            raise HTTPException(status_code=404, detail="Layer not found")
        return []
    skills = []
    for r in rows:
        skills.append(LayerSkillResponse(
            layer_id=r[0],
            skill_id=r[1],
            skill_name=r[2],
            skill_description=r[3] or "",
            skill_type=r[4] or "tool"
        ))
    return skills

# ----------------------------------------------------------------------
# New Phase 2 endpoints
# ----------------------------------------------------------------------
@router.post("/install", status_code=201)
async def install_layer(
    request: InstallLayerRequest,
    current_user=Depends(get_current_user)
):
    """Install a layer from a Git repository."""
    try:
        manager = LayerManager()
        layer_id = await manager.install_layer(request.git_url, request.version)
        return {"layer_id": layer_id, "message": "Layer installed successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/{layer_id}/enable", status_code=200)
async def enable_layer(
    layer_id: str,
    current_user=Depends(get_current_user)
):
    """Enable a layer (make its roles and skills available)."""
    try:
        manager = LayerManager()
        success = await manager.enable_layer(layer_id)
        if not success:
            raise HTTPException(status_code=404, detail="Layer not found")
        return {"status": "enabled"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/{layer_id}/disable", status_code=200)
async def disable_layer(
    layer_id: str,
    current_user=Depends(get_current_user)
):
    """Disable a layer."""
    manager = LayerManager()
    success = await manager.disable_layer(layer_id)
    if not success:
        raise HTTPException(status_code=404, detail="Layer not found")
    return {"status": "disabled"}

@router.get("/{layer_id}/config", response_model=LayerConfigResponse)
async def get_layer_config(
    layer_id: str,
    hive_id: Optional[str] = None,
    current_user=Depends(get_current_user)
):
    """Retrieve configuration for a layer (optionally per hive)."""
    manager = LayerManager()
    if not hive_id:
        raise HTTPException(status_code=400, detail="hive_id query parameter required")
    config = await manager.get_layer_config(layer_id, hive_id)
    if config is None:
        config = {}
    return LayerConfigResponse(config=config)

@router.put("/{layer_id}/config", status_code=200)
async def update_layer_config(
    layer_id: str,
    hive_id: Optional[str] = None,
    payload: LayerConfigUpdate = Body(...),
    current_user=Depends(get_current_user)
):
    """Update configuration for a layer in a specific hive."""
    if not hive_id:
        raise HTTPException(status_code=400, detail="hive_id query parameter required")
    manager = LayerManager()
    success = await manager.configure_layer(layer_id, hive_id, payload.config)
    if not success:
        raise HTTPException(status_code=404, detail="Layer not found")
    return {"status": "configured"}

@router.get("/{layer_id}/config-schema")
async def get_layer_config_schema(
    layer_id: str,
    current_user=Depends(get_current_user)
):
    """Return the JSON schema for layer configuration."""
    manager = LayerManager()
    schema = await manager.get_layer_config_schema(layer_id)
    if schema is None:
        return {}
    return schema

@router.get("/{layer_id}/loop-handlers")
async def list_layer_loop_handlers(
    layer_id: str,
    current_user=Depends(get_current_user)
):
    """List loop handlers registered by this layer."""
    manager = LayerManager()
    handlers = await manager.list_loop_handlers(layer_id)
    return handlers
