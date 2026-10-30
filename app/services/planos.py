"""Limites do plano Free (papel `professor`). Pro, Escola e admin não têm
limite — é o que o plano de negócio vende (README, seção 5)."""

from datetime import datetime

from fastapi import HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.dependencies import NIVEL_PAPEL, UsuarioAutenticado
from app.database import utc_now_naive
from app.models import Prova, Turma
from app.services import log_client

LIMITE_TURMAS_FREE = 1
LIMITE_PROVAS_POR_MES_FREE = 2


def _eh_free(usuario: UsuarioAutenticado) -> bool:
    return NIVEL_PAPEL.get(usuario.role, 0) < NIVEL_PAPEL["professor_pro"]


def _negar(request: Request, usuario: UsuarioAutenticado, limite: str, mensagem: str) -> None:
    # Mesmo evento das outras negações (acesso_negado:...): o admin vê no
    # log quem bateu no limite, o que é sinal de quem está perto de assinar.
    log_client.registrar_evento(
        usuario.id,
        f"acesso_negado:limite_free:{limite}",
        ip=request.client.host if request.client else None,
    )
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=mensagem)


def exigir_vaga_de_turma(db: Session, request: Request, usuario: UsuarioAutenticado) -> None:
    if not _eh_free(usuario):
        return
    total = db.query(func.count(Turma.id)).filter(Turma.usuario_id == usuario.id).scalar()
    if total >= LIMITE_TURMAS_FREE:
        _negar(request, usuario, "turmas", "O plano Free permite 1 turma. Assine o Pro para criar mais.")


def exigir_vaga_de_prova(db: Session, request: Request, usuario: UsuarioAutenticado) -> None:
    if not _eh_free(usuario):
        return
    agora = utc_now_naive()
    inicio_do_mes = datetime(agora.year, agora.month, 1)
    total = (
        db.query(func.count(Prova.id))
        .filter(Prova.usuario_id == usuario.id, Prova.criado_em >= inicio_do_mes)
        .scalar()
    )
    if total >= LIMITE_PROVAS_POR_MES_FREE:
        _negar(
            request,
            usuario,
            "provas",
            "O plano Free permite 2 provas por mês. Assine o Pro para criar mais.",
        )
