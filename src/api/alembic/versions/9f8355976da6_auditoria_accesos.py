"""auditoria_accesos

Revision ID: 9f8355976da6
Revises: 764260e423bf
Create Date: 2026-08-14 08:43:10.914622

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '9f8355976da6'
down_revision: Union[str, Sequence[str], None] = '764260e423bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('auditoria_accesos',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.Column('moodle_username', sa.String(), nullable=False),
        sa.Column('recurso', sa.String(), nullable=False),
        sa.Column('resultado', sa.String(), nullable=False),
        sa.Column('metadatos', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        schema='metrics'
    )
    op.create_index(op.f('ix_metrics_auditoria_accesos_moodle_username'), 'auditoria_accesos', ['moodle_username'], unique=False, schema='metrics')
    op.create_index(op.f('ix_metrics_auditoria_accesos_timestamp'), 'auditoria_accesos', ['timestamp'], unique=False, schema='metrics')

    # Trigger to prevent UPDATE and DELETE
    op.execute("""
    CREATE OR REPLACE FUNCTION metrics.prevent_auditoria_update_delete()
    RETURNS TRIGGER AS $$
    BEGIN
        RAISE EXCEPTION 'auditoria_accesos is append-only';
    END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("""
    CREATE TRIGGER trg_prevent_auditoria_update_delete
    BEFORE UPDATE OR DELETE ON metrics.auditoria_accesos
    FOR EACH ROW EXECUTE FUNCTION metrics.prevent_auditoria_update_delete();
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_auditoria_update_delete ON metrics.auditoria_accesos")
    op.execute("DROP FUNCTION IF EXISTS metrics.prevent_auditoria_update_delete()")
    op.drop_index(op.f('ix_metrics_auditoria_accesos_timestamp'), table_name='auditoria_accesos', schema='metrics')
    op.drop_index(op.f('ix_metrics_auditoria_accesos_moodle_username'), table_name='auditoria_accesos', schema='metrics')
    op.drop_table('auditoria_accesos', schema='metrics')
