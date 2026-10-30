from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, utc_now_naive


class Perfil(Base):
    """Perfil de rede social (atividade 6): bio e foto. O nome não mora
    aqui — é da tabela `usuarios`, do auth-service."""

    __tablename__ = "perfis"

    # Um perfil por usuário, então o próprio usuario_id é a PK. Sem
    # ForeignKey pra usuarios, pelo mesmo motivo das outras tabelas do usuário:
    # outro serviço, outro dono — o usuario_id é validado só pelo JWT.
    usuario_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    bio: Mapped[str | None] = mapped_column(String(280), nullable=True)
    # Só a chave do objeto no Garage (ex.: perfis/7/<uuid>.jpg) — o arquivo
    # em si nunca passa pelo banco. A URL é montada na hora de exibir.
    foto_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now_naive, onupdate=utc_now_naive, server_default=func.now()
    )
