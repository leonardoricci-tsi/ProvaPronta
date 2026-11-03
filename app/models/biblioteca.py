from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, utc_now_naive


class Pasta(Base):
    """Pasta da biblioteca de materiais (ex.: "1º ano — Matemática — 1º
    bimestre"). Raiz do isolamento da biblioteca, como a turma é da prova."""

    __tablename__ = "pastas"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now_naive, server_default=func.now()
    )

    materiais: Mapped[list["Material"]] = relationship(
        back_populates="pasta", cascade="all, delete-orphan", order_by="Material.nome"
    )

    @property
    def total_materiais(self) -> int:
        return len(self.materiais)


class Material(Base):
    """PDF da biblioteca. O arquivo mora no Garage; aqui só a chave do
    objeto (gerada pelo servidor), o nome original e o tamanho."""

    __tablename__ = "materiais"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Dono repetido aqui (além de vir pela pasta) pra filtrar direto na query
    # sem join — é o filtro do isolamento.
    usuario_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    pasta_id: Mapped[int] = mapped_column(
        ForeignKey("pastas.id", name="fk_materiais_pasta_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    chave: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    tamanho_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now_naive, server_default=func.now()
    )

    pasta: Mapped[Pasta] = relationship(back_populates="materiais")
