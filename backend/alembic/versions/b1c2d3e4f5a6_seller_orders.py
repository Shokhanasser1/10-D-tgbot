"""seller orders: every order knows its seller; shipments wait for the seller to be ready

Revision ID: b1c2d3e4f5a6
Revises: a9b8c7d6e5f4
Create Date: 2026-10-04 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = 'a9b8c7d6e5f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('orders', sa.Column('seller_id', sa.Integer(), nullable=True))
    # An order's seller is its products' seller (one per cart since Spec 9; the lowest id if an
    # old order ever mixed them).
    op.execute(
        "UPDATE orders SET seller_id = ("
        "  SELECT min(p.seller_id) FROM order_items oi"
        "  JOIN variants v ON v.id = oi.variant_id"
        "  JOIN products p ON p.id = v.product_id"
        "  WHERE oi.order_id = orders.id"
        ")"
    )
    # Orders without items have no products to ask: they go to a shop of their own.
    op.execute(
        "WITH main AS ("
        "  INSERT INTO sellers (name)"
        "  SELECT 'Main shop' WHERE EXISTS (SELECT 1 FROM orders WHERE seller_id IS NULL)"
        "  RETURNING id"
        ") UPDATE orders SET seller_id = (SELECT id FROM main) WHERE seller_id IS NULL"
    )
    op.alter_column('orders', 'seller_id', nullable=False)
    op.create_index(op.f('ix_orders_seller_id'), 'orders', ['seller_id'], unique=False)
    op.create_foreign_key(op.f('fk_orders_seller_id_sellers'), 'orders', 'sellers', ['seller_id'], ['id'], ondelete='RESTRICT')

    op.add_column('shipments', sa.Column('ready_at', sa.DateTime(timezone=True), nullable=True))
    # Shipments that exist already were in the pool (or past it): they stay ready.
    op.execute("UPDATE shipments SET ready_at = created_at")


def downgrade() -> None:
    """Downgrade schema."""
    # Orders still waiting for their seller then appear in the courier pool.
    op.drop_column('shipments', 'ready_at')
    op.drop_constraint(op.f('fk_orders_seller_id_sellers'), 'orders', type_='foreignkey')
    op.drop_index(op.f('ix_orders_seller_id'), table_name='orders')
    op.drop_column('orders', 'seller_id')
