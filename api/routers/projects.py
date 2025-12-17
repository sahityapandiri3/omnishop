"""
Projects API routes for saving and managing user design work
"""
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from schemas.projects import ProjectCreate, ProjectListItem, ProjectResponse, ProjectsListResponse, ProjectUpdate
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user
from core.database import get_db
from database.models import Project, ProjectStatus, User

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=ProjectsListResponse)
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all projects for the current user.
    Returns projects without large image data for fast loading.
    """
    # Get projects ordered by most recently updated
    query = select(Project).where(Project.user_id == current_user.id).order_by(Project.updated_at.desc())
    result = await db.execute(query)
    projects = result.scalars().all()

    # Get total count
    count_query = select(func.count()).select_from(Project).where(Project.user_id == current_user.id)
    count_result = await db.execute(count_query)
    total = count_result.scalar()

    # Convert to list items (without large image data)
    project_items = [
        ProjectListItem(
            id=p.id,
            name=p.name,
            status=p.status.value if p.status else "draft",  # Convert enum to string
            has_room_image=bool(p.room_image),
            has_visualization=bool(p.visualization_image),
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in projects
    ]

    return ProjectsListResponse(projects=project_items, total=total)


def _project_to_response(project: Project) -> ProjectResponse:
    """Convert a Project ORM object to a ProjectResponse, handling enum conversion."""
    return ProjectResponse(
        id=project.id,
        name=project.name,
        status=project.status.value if project.status else "draft",
        room_image=project.room_image,
        clean_room_image=project.clean_room_image,
        visualization_image=project.visualization_image,
        canvas_products=project.canvas_products,
        visualization_history=project.visualization_history,
        chat_session_id=project.chat_session_id,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new project for the current user.
    """
    project = Project(
        user_id=current_user.id,
        name=project_data.name,
    )

    db.add(project)
    await db.commit()
    await db.refresh(project)

    logger.info(f"Created project {project.id} for user {current_user.id}")

    return _project_to_response(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific project by ID.
    Returns full project data including images.
    """
    query = select(Project).where(
        Project.id == project_id,
        Project.user_id == current_user.id,
    )
    result = await db.execute(query)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return _project_to_response(project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    project_data: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a project (used for auto-save).
    Only updates fields that are provided.
    """
    query = select(Project).where(
        Project.id == project_id,
        Project.user_id == current_user.id,
    )
    result = await db.execute(query)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Update only provided fields
    update_data = project_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        # Handle status enum conversion
        if field == "status" and value is not None:
            value = ProjectStatus(value.upper()) if isinstance(value, str) else value
        setattr(project, field, value)

    # Always update the timestamp
    project.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(project)

    logger.debug(f"Updated project {project_id} (fields: {list(update_data.keys())})")

    return _project_to_response(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a project.
    """
    query = select(Project).where(
        Project.id == project_id,
        Project.user_id == current_user.id,
    )
    result = await db.execute(query)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    await db.delete(project)
    await db.commit()

    logger.info(f"Deleted project {project_id} for user {current_user.id}")

    return None


@router.get("/{project_id}/thumbnail")
async def get_project_thumbnail(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the visualization thumbnail for a project.
    Returns only the visualization image for efficient loading in project list.
    """
    query = select(Project.visualization_image).where(
        Project.id == project_id,
        Project.user_id == current_user.id,
    )
    result = await db.execute(query)
    visualization_image = result.scalar_one_or_none()

    if visualization_image is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or no visualization",
        )

    return {"visualization_image": visualization_image}
