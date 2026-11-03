"""add plano a assinaturas (qual dos planos pagos foi comprado)

Revision ID: d4e6f8a0b2c3
Revises: c3d5e7f9a1b2
Create Date: 2026-10-09 00:00:00.000000

Atividade 7: em vez de um único plano premium, os planos pagos são os
papéis do RBAC — `plano` guarda qual foi pago.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e6f8a0b2c3'
down_revision: Union[str, None] = 'c3d5e7f9a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('assinaturas', sa.Column('plano', sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column('assinaturas', 'plano')
