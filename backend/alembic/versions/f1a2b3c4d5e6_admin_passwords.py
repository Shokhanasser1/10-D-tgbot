"""admin passwords and roles

Revision ID: f1a2b3c4d5e6
Revises: e8f9a0b1c2d3
Create Date: 2026-09-29 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e8f9a0b1c2d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # New roles (manager, accountant, viewer) need nothing: the role column is a VARCHAR(20).
    op.add_column('admins', sa.Column('login', sa.String(length=32), nullable=True))
    op.add_column('admins', sa.Column('password_hash', sa.String(length=255), nullable=True))
    op.add_column('admins', sa.Column('must_change_password', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('admins', sa.Column('session_version', sa.Integer(), server_default='1', nullable=False))
    op.add_column('admins', sa.Column('failed_logins', sa.Integer(), server_default='0', nullable=False))
    op.add_column('admins', sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True))
    op.add_column('admins', sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint('uq_admins_login', 'admins', ['login'])


def downgrade() -> None:
    """Downgrade schema."""
    # The old schema only knows three roles; the new ones fall back to read-less dispatcher
    # rights would be wrong, so they are deactivated instead.
    op.execute(
        "UPDATE admins SET is_active = false, role = 'dispatcher' "
        "WHERE role IN ('manager', 'accountant', 'viewer')"
    )
    op.drop_constraint('uq_admins_login', 'admins', type_='unique')
    for column in ('password_changed_at', 'locked_until', 'failed_logins', 'session_version',
                   'must_change_password', 'password_hash', 'login'):
        op.drop_column('admins', column)
