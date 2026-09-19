"""janela da primeira busca (alerts.min_item_id)

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-19 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.models  # noqa: F401  (tipos personalizados como UTCDateTime)


# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, Sequence[str], None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('alerts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('min_item_id', sa.BigInteger(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('alerts', schema=None) as batch_op:
        batch_op.drop_column('min_item_id')
