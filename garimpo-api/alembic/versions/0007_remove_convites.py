"""remove convites

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-19 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.models  # noqa: F401  (tipos personalizados como UTCDateTime)


# revision identifiers, used by Alembic.
revision: str = '0007'
down_revision: Union[str, Sequence[str], None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_table('invites')


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table(
        'invites',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('code_hash', sa.String(length=64), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('expires_at', app.models.UTCDateTime(timezone=True), nullable=False),
        sa.Column('used_at', app.models.UTCDateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code_hash'),
    )
