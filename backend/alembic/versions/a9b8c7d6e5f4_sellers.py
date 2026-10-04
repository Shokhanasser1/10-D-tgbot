"""sellers: every product belongs to one; seller accounts in the admin panel

Revision ID: a9b8c7d6e5f4
Revises: f1a2b3c4d5e6
Create Date: 2026-10-04 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9b8c7d6e5f4'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('sellers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('phone', sa.String(length=32), nullable=True),
    sa.Column('pickup_address', sa.String(length=500), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sellers'))
    )

    op.add_column('products', sa.Column('seller_id', sa.Integer(), nullable=True))
    # Products that existed before sellers all go to one shop, which the owner can rename.
    # With an empty catalog no shop is created.
    op.execute(
        "WITH main AS ("
        "  INSERT INTO sellers (name) SELECT 'Main shop' WHERE EXISTS (SELECT 1 FROM products)"
        "  RETURNING id"
        ") UPDATE products SET seller_id = (SELECT id FROM main)"
    )
    op.alter_column('products', 'seller_id', nullable=False)
    op.create_index(op.f('ix_products_seller_id'), 'products', ['seller_id'], unique=False)
    op.create_foreign_key(op.f('fk_products_seller_id_sellers'), 'products', 'sellers', ['seller_id'], ['id'], ondelete='RESTRICT')

    op.add_column('admins', sa.Column('seller_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_admins_seller_id'), 'admins', ['seller_id'], unique=False)
    op.create_foreign_key(op.f('fk_admins_seller_id_sellers'), 'admins', 'sellers', ['seller_id'], ['id'], ondelete='RESTRICT')
    op.create_check_constraint(op.f('ck_admins_seller_role'), 'admins', "(role = 'seller') = (seller_id IS NOT NULL)")


def downgrade() -> None:
    """Downgrade schema."""
    # The previous schema has no seller role: those accounts cannot survive the way back.
    op.execute("DELETE FROM admins WHERE role = 'seller'")
    op.drop_constraint(op.f('ck_admins_seller_role'), 'admins', type_='check')
    op.drop_constraint(op.f('fk_admins_seller_id_sellers'), 'admins', type_='foreignkey')
    op.drop_index(op.f('ix_admins_seller_id'), table_name='admins')
    op.drop_column('admins', 'seller_id')
    op.drop_constraint(op.f('fk_products_seller_id_sellers'), 'products', type_='foreignkey')
    op.drop_index(op.f('ix_products_seller_id'), table_name='products')
    op.drop_column('products', 'seller_id')
    op.drop_table('sellers')
