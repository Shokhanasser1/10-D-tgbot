"""seller money: commission rates, earnings on delivery, recorded payouts

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-10-04 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2d3e4f5a6b7'
down_revision: Union[str, Sequence[str], None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('sellers', sa.Column('commission_percent', sa.Numeric(precision=5, scale=2), server_default='10', nullable=False))
    op.create_check_constraint(op.f('ck_sellers_commission_range'), 'sellers', 'commission_percent BETWEEN 0 AND 100')

    # Orders keep the rate of the day they were placed; existing ones take their seller's.
    op.add_column('orders', sa.Column('commission_percent', sa.Numeric(precision=5, scale=2), nullable=True))
    op.execute(
        "UPDATE orders SET commission_percent = sellers.commission_percent "
        "FROM sellers WHERE sellers.id = orders.seller_id"
    )
    op.alter_column('orders', 'commission_percent', nullable=False)

    op.create_table('seller_earnings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('seller_id', sa.Integer(), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('goods_total', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('commission_percent', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('commission', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('earned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], name=op.f('fk_seller_earnings_order_id_orders'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['seller_id'], ['sellers.id'], name=op.f('fk_seller_earnings_seller_id_sellers'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_seller_earnings')),
    sa.UniqueConstraint('order_id', name=op.f('uq_seller_earnings_order_id'))
    )
    op.create_index(op.f('ix_seller_earnings_seller_id'), 'seller_earnings', ['seller_id'], unique=False)

    op.create_table('seller_payouts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('seller_id', sa.Integer(), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('note', sa.String(length=500), nullable=True),
    sa.Column('created_by', sa.BigInteger(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('amount > 0', name=op.f('ck_seller_payouts_positive_amount')),
    sa.ForeignKeyConstraint(['seller_id'], ['sellers.id'], name=op.f('fk_seller_payouts_seller_id_sellers'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_seller_payouts'))
    )
    op.create_index(op.f('ix_seller_payouts_seller_id'), 'seller_payouts', ['seller_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_seller_payouts_seller_id'), table_name='seller_payouts')
    op.drop_table('seller_payouts')
    op.drop_index(op.f('ix_seller_earnings_seller_id'), table_name='seller_earnings')
    op.drop_table('seller_earnings')
    op.drop_column('orders', 'commission_percent')
    op.drop_constraint(op.f('ck_sellers_commission_range'), 'sellers', type_='check')
    op.drop_column('sellers', 'commission_percent')
