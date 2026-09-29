"""stock reservation

Revision ID: c4f1a2b3d5e6
Revises: bbb147ebf681
Create Date: 2026-09-29 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4f1a2b3d5e6'
down_revision: Union[str, Sequence[str], None] = 'bbb147ebf681'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # NULL marks orders placed before reservations existed: they hold no stock.
    op.add_column('orders', sa.Column('reserved_until', sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        'ix_orders_pending_reserved_until',
        'orders',
        ['reserved_until'],
        postgresql_where=sa.text("status = 'pending_payment'"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_orders_pending_reserved_until', table_name='orders')
    op.drop_column('orders', 'reserved_until')
