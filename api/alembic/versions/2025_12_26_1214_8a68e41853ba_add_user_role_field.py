"""add_user_role_field

Revision ID: 8a68e41853ba
Revises: d8178f88dff1
Create Date: 2025-12-26 12:14:50.248329

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "8a68e41853ba"
down_revision: Union[str, Sequence[str], None] = "d8178f88dff1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add role field to users table for permission management."""
    # Create the enum type
    user_role = postgresql.ENUM("user", "admin", "super_admin", name="userrole", create_type=False)
    user_role.create(op.get_bind(), checkfirst=True)

    # Add role column with default 'user'
    op.add_column(
        "users",
        sa.Column("role", sa.Enum("user", "admin", "super_admin", name="userrole"), nullable=False, server_default="user"),
    )

    # Create index on role for faster queries
    op.create_index("ix_users_role", "users", ["role"])

    # Bootstrap first super admin
    op.execute(
        """
        UPDATE users
        SET role = 'super_admin'
        WHERE email = 'sahityapandiri3@gmail.com'
    """
    )


def downgrade() -> None:
    """Remove role field from users table."""
    # Drop the index
    op.drop_index("ix_users_role", table_name="users")

    # Drop the column
    op.drop_column("users", "role")

    # Drop the enum type
    user_role = postgresql.ENUM("user", "admin", "super_admin", name="userrole")
    user_role.drop(op.get_bind(), checkfirst=True)
