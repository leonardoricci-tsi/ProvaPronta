"""assinatura recorrente: status, valor mensal e eventos do Stripe já processados

Revision ID: e7a9c1d3f5b7
Revises: c3e5a7b9d1f2
Create Date: 2026-11-10 00:00:00.000000

Atividade 11 (SaaS completo): a assinatura passa a ser acompanhada pelos
webhooks (`customer.subscription.updated`, `invoice.payment_failed`), então
guarda o status do Stripe e o valor mensal (MRR no painel do admin). A
tabela `eventos_stripe` guarda o ID de cada evento processado, pra que o
mesmo evento entregue duas vezes não tenha efeito duas vezes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e7a9c1d3f5b7'
down_revision: Union[str, None] = 'c3e5a7b9d1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('assinaturas', sa.Column('status', sa.String(length=30), nullable=True))
    op.add_column('assinaturas', sa.Column('valor_mensal_centavos', sa.Integer(), nullable=True))
    # Assinaturas da atividade 7 que estão pagas continuam valendo.
    op.execute("UPDATE assinaturas SET status = 'active' WHERE premium = 1")
    op.create_table(
        'eventos_stripe',
        sa.Column('id', sa.String(length=255), primary_key=True),
        sa.Column('tipo', sa.String(length=100), nullable=False),
        sa.Column('recebido_em', sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('eventos_stripe')
    op.drop_column('assinaturas', 'valor_mensal_centavos')
    op.drop_column('assinaturas', 'status')
