"""limpa referências a arquivos do bucket antigo (bucket novo: provapronta-arquivos)

Revision ID: b9d1f3a5c7e9
Revises: a7c9e1f3b5d7
Create Date: 2026-11-03 00:00:00.000000

Atividade 10: o bucket do Garage mudou de nome e o novo começa vazio (o
Garage cria o bucket padrão na subida). Fotos de perfil e PDFs enviados
antes ficaram no bucket antigo, então as chaves gravadas aqui apontariam
pra objetos que não existem mais — imagem quebrada e link de PDF dando
404. Zera as referências: o perfil volta a mostrar as iniciais e a prova
volta a "sem material", prontos pra um envio novo.

Rodar DEPOIS do deploy com o bucket novo. Sem downgrade: as chaves antigas
não têm pra onde voltar.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'b9d1f3a5c7e9'
down_revision: Union[str, None] = 'a7c9e1f3b5d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE perfis SET foto_key = NULL WHERE foto_key IS NOT NULL")
    op.execute(
        "UPDATE provas SET material_key = NULL, material_nome = NULL WHERE material_key IS NOT NULL"
    )


def downgrade() -> None:
    pass
