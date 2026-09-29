"""payment methods

Revision ID: e8f9a0b1c2d3
Revises: d7e2f3a4b5c6
Create Date: 2026-09-29 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8f9a0b1c2d3'
down_revision: Union[str, Sequence[str], None] = 'd7e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_METHOD = sa.Enum('telegram', 'cash', 'stripe', name='paymentmethod', native_enum=False, length=20)


def upgrade() -> None:
    """Upgrade schema."""
    # Every order and payment so far went through Stripe.
    op.add_column('orders', sa.Column('payment_method', _METHOD, server_default='stripe', nullable=False))
    op.add_column('payments', sa.Column('method', _METHOD, server_default='stripe', nullable=False))
    op.add_column('payments', sa.Column('telegram_payment_charge_id', sa.String(length=255), nullable=True))
    op.add_column('payments', sa.Column('provider_payment_charge_id', sa.String(length=255), nullable=True))
    op.alter_column('payments', 'stripe_payment_intent_id', existing_type=sa.String(length=255), nullable=True)
    # RefundStatus gains manual_required: a non-native enum, so only the length could matter,
    # and the column is already long enough (VARCHAR(20)).


def downgrade() -> None:
    """Downgrade schema."""
    # Payments without a Stripe ID cannot exist in the old schema.
    op.execute("DELETE FROM payments WHERE stripe_payment_intent_id IS NULL")
    op.execute("UPDATE payments SET refund_status = 'pending' WHERE refund_status = 'manual_required'")
    op.alter_column('payments', 'stripe_payment_intent_id', existing_type=sa.String(length=255), nullable=False)
    op.drop_column('payments', 'provider_payment_charge_id')
    op.drop_column('payments', 'telegram_payment_charge_id')
    op.drop_column('payments', 'method')
    op.drop_column('orders', 'payment_method')
