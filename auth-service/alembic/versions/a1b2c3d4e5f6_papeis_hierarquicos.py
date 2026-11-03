"""papel usuario vira cinefilo, novos papeis nerd e stalker

Revision ID: a1b2c3d4e5f6
Revises: f3a8c1d94b2e
Create Date: 2026-09-01 00:00:00.000000

Atividade 4 (RBAC): o papel único "usuario" vira uma escada de papéis
(cinefilo < nerd < stalker < admin), cada um com mais
permissão que o anterior — "admin" é o topo, não um papel à parte.

Nota (atividade 10): o papel do topo do projeto anterior aparece aqui com
o nome neutro `stalker`. Todo banco existente já passou desta revisão (e
de b2c3d4e5f6a7, que troca os papéis pelos do ProvaPronta), então isso não
muda nenhum banco: num banco novo esse papel nunca existe.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f3a8c1d94b2e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('usuarios', 'role', server_default='cinefilo')
    op.execute("UPDATE usuarios SET role = 'cinefilo' WHERE role = 'usuario'")


def downgrade() -> None:
    op.execute("UPDATE usuarios SET role = 'usuario' WHERE role IN ('cinefilo', 'nerd', 'stalker')")
    op.alter_column('usuarios', 'role', server_default='usuario')
