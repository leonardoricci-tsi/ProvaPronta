"""papeis do ProvaPronta: professor < professor_pro < coordenador < admin

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-29 00:00:00.000000

Atividade 10: a mesma escada de papéis do RBAC, com os nomes do negócio.
Cada papel antigo vira o do mesmo degrau — quem pagava um plano continua
no plano equivalente, e admin continua admin.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (antigo, novo), do degrau mais baixo pro mais alto.
_PAPEIS = (
    ('cinefilo', 'professor'),
    ('nerd', 'professor_pro'),
    ('stalker_do_tomhanks', 'coordenador'),
)


def upgrade() -> None:
    op.alter_column('usuarios', 'role', server_default='professor')
    for antigo, novo in _PAPEIS:
        op.execute(f"UPDATE usuarios SET role = '{novo}' WHERE role = '{antigo}'")


def downgrade() -> None:
    for antigo, novo in _PAPEIS:
        op.execute(f"UPDATE usuarios SET role = '{antigo}' WHERE role = '{novo}'")
    op.alter_column('usuarios', 'role', server_default='cinefilo')
