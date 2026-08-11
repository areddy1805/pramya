"""Versioned API router aggregator."""

from fastapi import APIRouter

from app.api.v1 import crud, health, interviews, models

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(crud.router, tags=["candidates", "documents", "evidence"])
api_router.include_router(interviews.router, tags=["interviews"])
api_router.include_router(models.router, tags=["models"])
