"""Versioned API router aggregator."""

from fastapi import APIRouter

from app.api.v1 import crud, health

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(crud.router, tags=["candidates", "documents", "evidence"])
