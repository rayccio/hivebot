from fastapi import APIRouter
from .endpoints import health, agents, files, global_files, providers, system, known_providers, bridges, hives, auth, users, plan, tasks, skills, agent_skills, meta, evaluation

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(files.router, prefix="", tags=["files"])
api_router.include_router(global_files.router, prefix="/global-files", tags=["global-files"])
api_router.include_router(providers.router, prefix="/providers", tags=["providers"])
api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(known_providers.router, prefix="/known-providers", tags=["known-providers"])
api_router.include_router(bridges.router, prefix="/bridges", tags=["bridges"])
api_router.include_router(hives.router, prefix="/hives", tags=["hives"])
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(plan.router)
api_router.include_router(tasks.router)
api_router.include_router(skills.router)
api_router.include_router(agent_skills.router)
api_router.include_router(meta.router)
api_router.include_router(evaluation.router)
# internal router is now included directly in main.py
