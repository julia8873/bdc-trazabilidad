"""add_rubrica

Revision ID: 6d291a14e74e
Revises: 42b6cd0c195a
Create Date: 2026-09-08 07:34:18.078652

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '6d291a14e74e'
down_revision: Union[str, Sequence[str], None] = '42b6cd0c195a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('rubricas',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('curso_id', sa.Integer(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('instrucciones_agente', sa.String(), nullable=True),
    sa.Column('criterios', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('curso_id', 'version', name='uq_rubrica_curso_version'),
    schema='metrics'
    )
    op.create_index(op.f('ix_metrics_rubricas_curso_id'), 'rubricas', ['curso_id'], unique=False, schema='metrics')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_metrics_rubricas_curso_id'), table_name='rubricas', schema='metrics')
    op.drop_table('rubricas', schema='metrics')

