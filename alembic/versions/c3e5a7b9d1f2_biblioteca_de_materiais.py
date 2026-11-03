"""biblioteca de materiais: pastas e PDFs (materiais)

Revision ID: c3e5a7b9d1f2
Revises: b9d1f3a5c7e9
Create Date: 2026-11-03 00:00:00.000000

O professor organiza os PDFs (apostila, livro, slides) em pastas — ex.:
"1º ano — Matemática — 1º bimestre" — e gera questões a partir de uma
pasta, de um PDF ou de vários. Mesmo padrão da a7c9e1f3b5d7: o DDL mora em
db/003_biblioteca.sql e esta migration só executa aquele arquivo.
"""
from pathlib import Path
from typing import Sequence, Union

from alembic import op


revision: str = 'c3e5a7b9d1f2'
down_revision: Union[str, None] = 'b9d1f3a5c7e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCRIPT = Path(__file__).resolve().parents[2] / "db" / "003_biblioteca.sql"


def _comandos(sql: str) -> list[str]:
    sem_comentarios = "\n".join(
        linha for linha in sql.splitlines() if not linha.lstrip().startswith("--")
    )
    return [comando.strip() for comando in sem_comentarios.split(";") if comando.strip()]


def upgrade() -> None:
    for comando in _comandos(_SCRIPT.read_text(encoding="utf-8")):
        op.execute(comando)


def downgrade() -> None:
    # Os objetos no Garage ficam órfãos (o downgrade não fala com o storage).
    op.drop_table("materiais")
    op.drop_table("pastas")
