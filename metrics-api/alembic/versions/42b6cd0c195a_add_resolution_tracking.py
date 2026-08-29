"""add_resolution_tracking

Revision ID: 42b6cd0c195a
Revises: ba95be90ae97
Create Date: 2026-08-29 05:33:34.006824

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '42b6cd0c195a'
down_revision: Union[str, Sequence[str], None] = 'ba95be90ae97'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('discrepancias_auditoria', sa.Column('resuelta', sa.Integer(), nullable=False, server_default='0'), schema='metrics')
    op.add_column('discrepancias_auditoria', sa.Column('resuelta_at', sa.DateTime(), nullable=True), schema='metrics')
    op.add_column('discrepancias_auditoria', sa.Column('resuelta_por', sa.Integer(), nullable=True), schema='metrics')
    op.add_column('discrepancias_auditoria', sa.Column('commit_log_ref', sa.String(), nullable=True), schema='metrics')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('discrepancias_auditoria', 'commit_log_ref', schema='metrics')
    op.drop_column('discrepancias_auditoria', 'resuelta_por', schema='metrics')
    op.drop_column('discrepancias_auditoria', 'resuelta_at', schema='metrics')
    op.drop_column('discrepancias_auditoria', 'resuelta', schema='metrics')
