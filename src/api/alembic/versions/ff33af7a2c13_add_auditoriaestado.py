"""Add AuditoriaEstado

Revision ID: ff33af7a2c13
Revises: 1ff6eb9eab6b
Create Date: 2026-08-15 11:17:41.515569

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ff33af7a2c13'
down_revision: Union[str, Sequence[str], None] = '1ff6eb9eab6b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('auditoria_estado',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('moodle_user_id', sa.Integer(), nullable=False),
    sa.Column('moodle_course_id', sa.Integer(), nullable=False),
    sa.Column('repo_owner', sa.String(), nullable=False),
    sa.Column('repo_name', sa.String(), nullable=False),
    sa.Column('last_audited_timestamp', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    schema='metrics'
    )

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('auditoria_estado', schema='metrics')
