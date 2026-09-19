"""teste gratis e assinatura

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-19 12:00:00.000000

"""
from datetime import datetime, timedelta, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.models  # noqa: F401  (tipos personalizados como UTCDateTime)


# revision identifiers, used by Alembic.
revision: str = '0006'
down_revision: Union[str, Sequence[str], None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('trial_ends_at', app.models.UTCDateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('subscription_status', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('subscription_ends_at', app.models.UTCDateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('stripe_customer_id', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('stripe_subscription_id', sa.String(length=64), nullable=True))
        batch_op.create_index(batch_op.f('ix_users_stripe_customer_id'), ['stripe_customer_id'], unique=False)
    # Contas que já existem ganham 7 dias de teste a partir de agora.
    ends = datetime.now(timezone.utc) + timedelta(days=7)
    op.get_bind().execute(
        sa.text("UPDATE users SET trial_ends_at = :ends WHERE email_verified_at IS NOT NULL"), {"ends": ends}
    )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_stripe_customer_id'))
        batch_op.drop_column('stripe_subscription_id')
        batch_op.drop_column('stripe_customer_id')
        batch_op.drop_column('subscription_ends_at')
        batch_op.drop_column('subscription_status')
        batch_op.drop_column('trial_ends_at')
