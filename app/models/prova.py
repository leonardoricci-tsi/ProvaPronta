from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, utc_now_naive

STATUS_PROVA = ("rascunho", "pronta")


class Prova(Base):
    """Recurso principal do ProvaPronta: a prova que o professor monta pra
    uma turma, com as questões e o PDF do material de onde elas saíram."""

    __tablename__ = "provas"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Dono (o professor). Vem do JWT na criação, nunca do corpo.
    usuario_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    # RESTRICT: apagar uma turma que já tem prova é recusado (409) em vez
    # de levar as provas junto sem ninguém perceber.
    turma_id: Mapped[int] = mapped_column(
        ForeignKey("turmas.id", name="fk_provas_turma_id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    data_aplicacao: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="rascunho", server_default="rascunho"
    )
    # PDF do material (livro, apostila) no Garage — o banco guarda só a
    # chave do objeto e o nome original, nunca o arquivo.
    material_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    material_nome: Mapped[str | None] = mapped_column(String(255), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now_naive, server_default=func.now()
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now_naive, onupdate=utc_now_naive, server_default=func.now()
    )

    turma: Mapped["Turma"] = relationship(back_populates="provas")  # noqa: F821
    questoes: Mapped[list["Questao"]] = relationship(
        back_populates="prova", cascade="all, delete-orphan", order_by="Questao.ordem"
    )


class Questao(Base):
    """Questão de múltipla escolha. O gabarito (`resposta_correta`, índice
    da alternativa certa) é do professor: só aparece pra ele, nunca na
    folha do aluno."""

    __tablename__ = "questoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    prova_id: Mapped[int] = mapped_column(
        ForeignKey("provas.id", name="fk_questoes_prova_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)
    enunciado: Mapped[str] = mapped_column(Text, nullable=False)
    # Lista de textos das alternativas, na ordem (A, B, C...).
    alternativas: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    resposta_correta: Mapped[int] = mapped_column(Integer, nullable=False)
    # Assunto (ex.: "Citologia") — base do relatório "em que a turma foi mal".
    assunto: Mapped[str | None] = mapped_column(String(100), nullable=True)

    prova: Mapped[Prova] = relationship(back_populates="questoes")
