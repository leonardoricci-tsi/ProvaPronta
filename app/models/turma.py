from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, utc_now_naive


class Turma(Base):
    """Turma do professor (ex.: "1º A — Biologia"). É a raiz do
    isolamento: alunos e provas pertencem a uma turma, e a turma pertence
    a um professor (`usuario_id`)."""

    __tablename__ = "turmas"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Dono da turma. Sem ForeignKey pra usuarios, igual a `perfis` e
    # `assinaturas`: a tabela é do auth-service, o usuario_id vem do JWT.
    usuario_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    disciplina: Mapped[str] = mapped_column(String(100), nullable=False)
    escola: Mapped[str | None] = mapped_column(String(150), nullable=True)
    ano_letivo: Mapped[int] = mapped_column(Integer, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now_naive, server_default=func.now()
    )

    alunos: Mapped[list["Aluno"]] = relationship(
        back_populates="turma", cascade="all, delete-orphan", order_by="Aluno.numero_chamada"
    )
    provas: Mapped[list["Prova"]] = relationship(back_populates="turma")  # noqa: F821

    @property
    def total_alunos(self) -> int:
        return len(self.alunos)


class Aluno(Base):
    """Aluno de uma turma. Só o mínimo (LGPD, muitos são menores de idade):
    nome e número de chamada — nada de CPF, e-mail ou foto."""

    __tablename__ = "alunos"
    __table_args__ = (
        UniqueConstraint("turma_id", "numero_chamada", name="uq_aluno_turma_numero"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    turma_id: Mapped[int] = mapped_column(
        ForeignKey("turmas.id", name="fk_alunos_turma_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    numero_chamada: Mapped[int] = mapped_column(Integer, nullable=False)

    turma: Mapped[Turma] = relationship(back_populates="alunos")
