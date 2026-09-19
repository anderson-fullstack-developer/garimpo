"""preferencias do usuario (pais, idioma, moeda)

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-19 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.models  # noqa: F401  (tipos personalizados como UTCDateTime)


# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: Union[str, Sequence[str], None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('country', sa.String(length=2), nullable=True))
        batch_op.add_column(sa.Column('language', sa.String(length=2), server_default='pt', nullable=False))
        batch_op.add_column(sa.Column('currency', sa.String(length=3), server_default='EUR', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('currency')
        batch_op.drop_column('language')
        batch_op.drop_column('country')
