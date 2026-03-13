from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from ....services.skill_manager import SkillManager
from ....services.skill_suggestion_manager import SkillSuggestionManager
from ....models.skill import Skill, SkillCreate, SkillVersion, SkillVersionCreate, SkillType, SkillVisibility, SkillSuggestion, SkillSuggestionCreate

router = APIRouter(prefix="/skills", tags=["skills"])

async def get_skill_manager():
    return SkillManager()

async def get_suggestion_manager():
    return SkillSuggestionManager()

@router.post("", response_model=Skill)
async def create_skill(skill_in: SkillCreate, manager: SkillManager = Depends(get_skill_manager)):
    return await manager.create_skill(skill_in)

@router.get("", response_model=List[Skill])
async def list_skills(
    visibility: Optional[SkillVisibility] = Query(None),
    author_id: Optional[str] = Query(None),
    manager: SkillManager = Depends(get_skill_manager)
):
    return await manager.list_skills(visibility, author_id)

@router.get("/{skill_id}", response_model=Skill)
async def get_skill(skill_id: str, manager: SkillManager = Depends(get_skill_manager)):
    skill = await manager.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill

@router.patch("/{skill_id}", response_model=Skill)
async def update_skill(skill_id: str, updates: dict, manager: SkillManager = Depends(get_skill_manager)):
    skill = await manager.update_skill(skill_id, **updates)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill

@router.delete("/{skill_id}", status_code=204)
async def delete_skill(skill_id: str, manager: SkillManager = Depends(get_skill_manager)):
    deleted = await manager.delete_skill(skill_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Skill not found")

@router.post("/{skill_id}/versions", response_model=SkillVersion)
async def create_version(skill_id: str, version_in: SkillVersionCreate, manager: SkillManager = Depends(get_skill_manager)):
    try:
        return await manager.create_version(skill_id, version_in)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{skill_id}/versions", response_model=List[SkillVersion])
async def list_versions(skill_id: str, manager: SkillManager = Depends(get_skill_manager)):
    return await manager.list_versions(skill_id)

@router.get("/versions/{version_id}", response_model=SkillVersion)
async def get_version(version_id: str, manager: SkillManager = Depends(get_skill_manager)):
    version = await manager.get_version(version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    return version

@router.patch("/versions/{version_id}", response_model=SkillVersion)
async def update_version(version_id: str, updates: dict, manager: SkillManager = Depends(get_skill_manager)):
    version = await manager.update_version(version_id, **updates)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    return version

# --- Skill Suggestion Endpoints ---
@router.get("/suggestions", response_model=List[SkillSuggestion])
async def list_suggestions(
    manager: SkillSuggestionManager = Depends(get_suggestion_manager)
):
    return await manager.get_all_unresolved()

@router.post("/suggestions/{suggestion_id}/create-skill", response_model=Skill)
async def create_skill_from_suggestion(
    suggestion_id: str,
    manager: SkillSuggestionManager = Depends(get_suggestion_manager)
):
    skill = await manager.create_skill_from_suggestion(suggestion_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Suggestion not found or already resolved")
    return skill

@router.delete("/suggestions/{suggestion_id}", status_code=204)
async def delete_suggestion(
    suggestion_id: str,
    manager: SkillSuggestionManager = Depends(get_suggestion_manager)
):
    deleted = await manager.delete_suggestion(suggestion_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Suggestion not found")
