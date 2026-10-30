"""dominio do ProvaPronta: turmas, alunos, provas, questoes

Revision ID: a7c9e1f3b5d7
Revises: f6a8b0c2d4e5
Create Date: 2026-10-29 00:00:00.000000

Atividade 10: o DDL mora em db/001_dominio.sql (o script versionado que dá
pra ler e aplicar na mão); esta migration só executa aquele arquivo e
registra a versão no alembic_version — é o mesmo SQL em dev, no CI e em
produção.
"""
from pathlib import Path
from typing import Sequence, Union

from alembic import op


revision: str = 'a7c9e1f3b5d7'
down_revision: Union[str, None] = 'f6a8b0c2d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCRIPT = Path(__file__).resolve().parents[2] / "db" / "001_dominio.sql"


def _comandos(sql: str) -> list[str]:
    """Separa o script em comandos: tira os comentários de linha (`--`) e
    corta no `;` — o driver executa um comando por vez."""
    sem_comentarios = "\n".join(
        linha for linha in sql.splitlines() if not linha.lstrip().startswith("--")
    )
    return [comando.strip() for comando in sem_comentarios.split(";") if comando.strip()]


def upgrade() -> None:
    for comando in _comandos(_SCRIPT.read_text(encoding="utf-8")):
        op.execute(comando)


def downgrade() -> None:
    # Ordem inversa das FKs: filhas antes das mães.
    for tabela in ("questoes", "provas", "alunos", "turmas"):
        op.drop_table(tabela)
