"""catalogo_conceptos

Migración del catálogo normalizado de conceptos (Fase 2 v3).

Revision ID: 764260e423bf
Revises: 9975d20fcbec
Create Date: 2026-08-13 12:45:21.990378

Cambios respecto a la baseline (9975d20fcbec):
1. Nueva tabla `conceptos`: catálogo normalizado con (curso_id, nombre) únicos.
2. La tabla `conceptos_detectados` se recrea (DROP + CREATE) para sustituir la
   columna `concepto` (String, texto libre) por `concepto_id` (UUID, FK real
   hacia conceptos.id).

Decisión documentada: se usa DROP/CREATE en lugar de ALTER porque en fase de
desarrollo no hay datos reales de alumnos. Si se ejecutara con datos ya cargados,
haría falta una migración de datos explícita (leer concepto String → buscar/crear
en conceptos → escribir concepto_id) ANTES del DROP. Ver docs/esquema-metrics.md.

NOTA IMPORTANTE: el autogenerate de Alembic generó esta migración cuando la BD
estaba en estado `base` (sin tablas), por lo que incluyó incorrectamente todas las
tablas del esquema. Esta migración fue reescrita manualmente para contener
únicamente el delta respecto a la baseline: solo se toca `conceptos` y
`conceptos_detectados`. Esta es la aplicación de la regla de migraciones aditivas
documentada en docs/integracion-bdc.md §7.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '764260e423bf'
down_revision: Union[str, Sequence[str], None] = '9975d20fcbec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Añade catálogo de conceptos y actualiza conceptos_detectados.
    Solo toca las dos tablas afectadas; el resto del esquema no se modifica.
    """
    # 1. Tabla conceptos (nueva)
    op.create_table(
        'conceptos',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('nombre', sa.String(), nullable=False),
        sa.Column('curso_id', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('curso_id', 'nombre', name='uq_concepto_curso_nombre'),
        schema='metrics',
    )

    # 2. Eliminar conceptos_detectados versión con texto libre...
    op.drop_index(
        op.f('ix_metrics_conceptos_detectados_interaccion_id'),
        table_name='conceptos_detectados',
        schema='metrics',
    )
    op.drop_table('conceptos_detectados', schema='metrics')

    # ...y crear versión con FK real hacia conceptos.id
    op.create_table(
        'conceptos_detectados',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('interaccion_id', sa.UUID(), nullable=False),
        sa.Column('concepto_id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ['interaccion_id'], ['metrics.interacciones.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['concepto_id'], ['metrics.conceptos.id'], ondelete='RESTRICT'
        ),
        sa.PrimaryKeyConstraint('id'),
        schema='metrics',
    )
    op.create_index(
        op.f('ix_metrics_conceptos_detectados_interaccion_id'),
        'conceptos_detectados',
        ['interaccion_id'],
        unique=False,
        schema='metrics',
    )
    op.create_index(
        op.f('ix_metrics_conceptos_detectados_concepto_id'),
        'conceptos_detectados',
        ['concepto_id'],
        unique=False,
        schema='metrics',
    )


def downgrade() -> None:
    """
    Revierte al esquema baseline: elimina conceptos y restaura
    conceptos_detectados con columna concepto (String, texto libre).
    """
    # Eliminar la versión con FK
    op.drop_index(
        op.f('ix_metrics_conceptos_detectados_concepto_id'),
        table_name='conceptos_detectados',
        schema='metrics',
    )
    op.drop_index(
        op.f('ix_metrics_conceptos_detectados_interaccion_id'),
        table_name='conceptos_detectados',
        schema='metrics',
    )
    op.drop_table('conceptos_detectados', schema='metrics')

    # Eliminar catálogo (ya no hay FKs que lo referencien)
    op.drop_table('conceptos', schema='metrics')

    # Restaurar conceptos_detectados con columna concepto (String, texto libre)
    op.create_table(
        'conceptos_detectados',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('interaccion_id', sa.UUID(), nullable=False),
        sa.Column('concepto', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ['interaccion_id'], ['metrics.interacciones.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
        schema='metrics',
    )
    op.create_index(
        op.f('ix_metrics_conceptos_detectados_interaccion_id'),
        'conceptos_detectados',
        ['interaccion_id'],
        unique=False,
        schema='metrics',
    )
