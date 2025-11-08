"""
Authentication routes.
"""

from fastapi import APIRouter, Depends
from app.auth import get_current_user

router = APIRouter()


@router.get("/me")
async def get_current_user_info(clerk_user_id: str = Depends(get_current_user)):
    """Get current authenticated user info."""
    return {"clerk_user_id": clerk_user_id}

