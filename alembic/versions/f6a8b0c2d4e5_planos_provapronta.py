"""planos pagos com os nomes do ProvaPronta (professor_pro, coordenador)

Revision ID: f6a8b0c2d4e5
Revises: e5f7a9b1c3d4
Create Date: 2026-10-29 00:00:00.000000

Atividade 10: `assinaturas.plano` guarda o papel que foi pago — acompanha
a troca de nomes dos papéis no auth-service (nerd -> professor_pro,
stalker_do_tomhanks -> coordenador).
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'f6a8b0c2d4e5'
down_revision: Union[str, None] = 'e5f7a9b1c3d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PLANOS = (('nerd', 'professor_pro'), ('stalker_do_tomhanks', 'coordenador'))


def upgrade() -> None:
    for antigo, novo in _PLANOS:
        op.execute(f"UPDATE assinaturas SET plano = '{novo}' WHERE plano = '{antigo}'")


def downgrade() -> None:
    for antigo, novo in _PLANOS:
        op.execute(f"UPDATE assinaturas SET plano = '{antigo}' WHERE plano = '{novo}'")
