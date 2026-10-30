"""drop favoritos e comentarios (fim do catálogo de filmes)

Revision ID: e5f7a9b1c3d4
Revises: d4e6f8a0b2c3
Create Date: 2026-10-29 00:00:00.000000

Atividade 10: o catálogo de filmes sai e o ProvaPronta entra. Favoritos e
comentários eram sobre filmes da TMDB e não têm equivalente no negócio
novo — as tabelas saem. O histórico continua no git (e o downgrade
recria as duas, vazias, com o esquema que tinham no fim).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f7a9b1c3d4'
down_revision: Union[str, None] = 'd4e6f8a0b2c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table('favoritos')
    op.drop_table('comentarios')


def downgrade() -> None:
    op.create_table('comentarios',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('tmdb_movie_id', sa.Integer(), nullable=False),
    sa.Column('texto', sa.Text(), nullable=False),
    sa.Column('criado_em', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('titulo', sa.String(length=500), nullable=True),
    sa.Column('poster_path', sa.String(length=255), nullable=True),
    sa.Column('nome_usuario', sa.String(length=255), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_comentarios_tmdb_movie_id'), 'comentarios', ['tmdb_movie_id'], unique=False)
    op.create_index(op.f('ix_comentarios_usuario_id'), 'comentarios', ['usuario_id'], unique=False)
    op.create_table('favoritos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('tmdb_movie_id', sa.Integer(), nullable=False),
    sa.Column('titulo', sa.String(length=500), nullable=False),
    sa.Column('poster_path', sa.String(length=255), nullable=True),
    sa.Column('criado_em', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('usuario_id', 'tmdb_movie_id', name='uq_favorito_usuario_filme')
    )
    op.create_index(op.f('ix_favoritos_usuario_id'), 'favoritos', ['usuario_id'], unique=False)
