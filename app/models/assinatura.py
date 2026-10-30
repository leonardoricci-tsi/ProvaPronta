from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, false, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, utc_now_naive


class Assinatura(Base):
    """Plano pago (atividade 7). Quem nunca pagou não tem linha aqui — está
    no plano gratuito (Free, papel `professor`).

    Dado de cartão NÃO mora aqui (nem em lugar nenhum deste sistema): o
    número, CVV e validade são digitados na página hospedada pelo Stripe e
    nunca chegam no backend. Só ficam os IDs que o Stripe devolve, pra
    saber de quem é cada cliente/assinatura quando o webhook chegar."""

    __tablename__ = "assinaturas"

    # Uma assinatura por usuário — mesmo esquema de `perfis`: usuario_id é a
    # PK, sem ForeignKey pra usuarios (tabela de outro serviço).
    usuario_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    # Só vira True pelo webhook do Stripe, com assinatura validada — nunca
    # pela volta do navegador do checkout (essa URL qualquer um abre).
    premium: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    # Qual plano foi pago — é o papel que o usuário recebe no auth-service
    # (professor_pro ou coordenador). Vazio quando a assinatura acabou.
    plano: Mapped[str | None] = mapped_column(String(50), nullable=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now_naive, onupdate=utc_now_naive, server_default=func.now()
    )
