"""
Permissions API routes for managing user roles (Super Admin only)
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import require_super_admin
from core.database import get_db
from database.models import SystemSettings, User, UserRole

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/permissions", tags=["permissions"])


class UserRoleUpdate(BaseModel):
    """Schema for updating a user's role"""

    role: str  # "user", "admin", or "super_admin"


class UserActiveUpdate(BaseModel):
    """Schema for toggling a user's active status"""

    is_active: bool


class WhitelistSettings(BaseModel):
    """Schema for whitelist settings"""

    enabled: bool
    emails: list[str]


class UserListItem(BaseModel):
    """Schema for user in list response"""

    id: str
    email: str
    name: Optional[str]
    role: str
    is_active: bool
    created_at: str

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Schema for paginated user list"""

    users: list[UserListItem]
    total: int
    page: int
    size: int


@router.get("/users", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    role: Optional[str] = Query(None, description="Filter by role: user, admin, super_admin"),
    search: Optional[str] = Query(None, description="Search by email"),
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    List all users with their roles (paginated, searchable by email).
    Only accessible by super admins.
    """
    try:
        # Build base query
        query = select(User)

        # Apply role filter
        if role:
            try:
                role_enum = UserRole(role)
                query = query.where(User.role == role_enum)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid role: {role}")

        # Apply email search
        if search:
            query = query.where(User.email.ilike(f"%{search}%"))

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination and ordering
        query = query.order_by(User.created_at.desc())
        query = query.offset((page - 1) * size).limit(size)

        # Execute query
        result = await db.execute(query)
        users = result.scalars().all()

        return UserListResponse(
            users=[
                UserListItem(
                    id=user.id,
                    email=user.email,
                    name=user.name,
                    role=user.role.value if hasattr(user.role, "value") else str(user.role),
                    is_active=user.is_active,
                    created_at=user.created_at.isoformat(),
                )
                for user in users
            ],
            total=total,
            page=page,
            size=size,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing users: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching users")


@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific user's details and role.
    Only accessible by super admins.
    """
    try:
        query = select(User).where(User.id == user_id)
        result = await db.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            "is_active": user.is_active,
            "auth_provider": user.auth_provider,
            "created_at": user.created_at.isoformat(),
            "last_login": user.last_login.isoformat() if user.last_login else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching user")


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    role_update: UserRoleUpdate,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a user's role.
    Only accessible by super admins.
    Cannot change your own role.
    """
    try:
        # Prevent self-role-change
        if user_id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot change your own role")

        # Validate role
        try:
            new_role = UserRole(role_update.role)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid role: {role_update.role}. Must be 'user', 'admin', or 'super_admin'"
            )

        # Find user
        query = select(User).where(User.id == user_id)
        result = await db.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        old_role = user.role.value if hasattr(user.role, "value") else str(user.role)

        # Update role
        user.role = new_role
        await db.commit()

        logger.info(f"User {user.email} role changed from {old_role} to {new_role.value} by {current_user.email}")

        return {
            "message": "User role updated successfully",
            "user_id": user_id,
            "email": user.email,
            "old_role": old_role,
            "new_role": new_role.value,
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating user role: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error updating user role")


@router.put("/users/{user_id}/active")
async def toggle_user_active(
    user_id: str,
    update: UserActiveUpdate,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Toggle a user's active status (block/unblock).
    Only accessible by super admins.
    Cannot block yourself or other super admins.
    """
    try:
        # Prevent self-block
        if user_id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot change your own active status")

        # Find user
        query = select(User).where(User.id == user_id)
        result = await db.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Prevent blocking other super admins
        user_role = user.role.value if hasattr(user.role, "value") else str(user.role)
        if user_role == "super_admin" and not update.is_active:
            raise HTTPException(status_code=400, detail="Cannot block a super admin")

        user.is_active = update.is_active
        await db.commit()

        action = "unblocked" if update.is_active else "blocked"
        logger.info(f"User {user.email} {action} by {current_user.email}")

        return {
            "message": f"User {action} successfully",
            "user_id": user_id,
            "email": user.email,
            "is_active": update.is_active,
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error toggling user active status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error updating user status")


# ============================================================================
# Whitelist Settings Endpoints
# ============================================================================


@router.get("/settings/whitelist", response_model=WhitelistSettings)
async def get_whitelist_settings(
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the current whitelist settings.
    Returns enabled status and list of whitelisted emails.
    """
    try:
        result = await db.execute(select(SystemSettings).where(SystemSettings.key == "whitelist"))
        setting = result.scalar_one_or_none()

        if not setting:
            return WhitelistSettings(enabled=False, emails=[])

        value = setting.value or {}
        return WhitelistSettings(
            enabled=value.get("enabled", False),
            emails=value.get("emails", []),
        )

    except Exception as e:
        logger.error(f"Error fetching whitelist settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching whitelist settings")


@router.put("/settings/whitelist", response_model=WhitelistSettings)
async def update_whitelist_settings(
    settings: WhitelistSettings,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Update whitelist settings (enable/disable and manage email list).
    Only accessible by super admins.
    """
    try:
        # Normalize emails to lowercase and deduplicate
        normalized_emails = list(set(e.strip().lower() for e in settings.emails if e.strip()))

        result = await db.execute(select(SystemSettings).where(SystemSettings.key == "whitelist"))
        setting = result.scalar_one_or_none()

        value = {"enabled": settings.enabled, "emails": normalized_emails}

        if setting:
            setting.value = value
            setting.updated_by = current_user.id
        else:
            setting = SystemSettings(
                key="whitelist",
                value=value,
                updated_by=current_user.id,
            )
            db.add(setting)

        await db.commit()

        logger.info(
            f"Whitelist settings updated by {current_user.email}: "
            f"enabled={settings.enabled}, emails_count={len(normalized_emails)}"
        )

        return WhitelistSettings(enabled=settings.enabled, emails=normalized_emails)

    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating whitelist settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error updating whitelist settings")
