from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import UsuarioAutenticado, get_current_user
from app.database import get_db
from app.models import Aluno, Prova, Turma
from app.openapi_responses import (
    RESP_401,
    RESP_403_LIMITE_FREE,
    RESP_404,
    RESP_409_ALUNO_NUMERO,
    RESP_409_TURMA_COM_PROVA,
)
from app.routers._ownership import get_owned_or_404
from app.schemas.turma import AlunoIn, AlunoOut, TurmaDetalheOut, TurmaIn, TurmaOut, TurmaUpdateIn
from app.services import log_client, planos

router = APIRouter(prefix="/turmas", tags=["turmas"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=list[TurmaOut], responses=RESP_401)
def listar_turmas(
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Turma]:
    """Só as turmas do usuário logado — o filtro pelo dono está na query,
    não na tela."""
    return (
        db.query(Turma)
        .options(selectinload(Turma.alunos))
        .filter(Turma.usuario_id == usuario_atual.id)
        .order_by(Turma.ano_letivo.desc(), Turma.nome)
        .all()
    )


@router.post(
    "",
    response_model=TurmaDetalheOut,
    status_code=status.HTTP_201_CREATED,
    responses=RESP_401 | RESP_403_LIMITE_FREE,
)
def criar_turma(
    dados: TurmaIn,
    request: Request,
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Turma:
    planos.exigir_vaga_de_turma(db, request, usuario_atual)
    turma = Turma(usuario_id=usuario_atual.id, **dados.model_dump())
    db.add(turma)
    db.commit()
    log_client.registrar_evento(usuario_atual.id, f"turma_criada:{turma.id}", ip=_ip(request))
    return turma


@router.get("/{turma_id}", response_model=TurmaDetalheOut, responses=RESP_401 | RESP_404)
def detalhar_turma(
    turma_id: int,
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Turma:
    return get_owned_or_404(db, Turma, turma_id, usuario_atual.id)


@router.patch("/{turma_id}", response_model=TurmaDetalheOut, responses=RESP_401 | RESP_404)
def editar_turma(
    turma_id: int,
    dados: TurmaUpdateIn,
    request: Request,
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Turma:
    turma = get_owned_or_404(db, Turma, turma_id, usuario_atual.id)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(turma, campo, valor)
    db.commit()
    log_client.registrar_evento(usuario_atual.id, f"turma_editada:{turma.id}", ip=_ip(request))
    return turma


@router.delete(
    "/{turma_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=RESP_401 | RESP_404 | RESP_409_TURMA_COM_PROVA,
)
def remover_turma(
    turma_id: int,
    request: Request,
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Os alunos saem junto (CASCADE). Provas não: com prova, 409 — a FK
    é RESTRICT justamente pra ninguém perder prova sem querer."""
    turma = get_owned_or_404(db, Turma, turma_id, usuario_atual.id)
    if db.query(Prova.id).filter(Prova.turma_id == turma.id).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A turma tem provas: apague as provas antes de apagar a turma",
        )
    db.delete(turma)
    db.commit()
    log_client.registrar_evento(usuario_atual.id, f"turma_removida:{turma_id}", ip=_ip(request))


@router.post(
    "/{turma_id}/alunos",
    response_model=AlunoOut,
    status_code=status.HTTP_201_CREATED,
    responses=RESP_401 | RESP_404 | RESP_409_ALUNO_NUMERO,
)
def adicionar_aluno(
    turma_id: int,
    dados: AlunoIn,
    request: Request,
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Aluno:
    # O aluno não tem dono próprio: é da turma. Conferir a turma pelo dono
    # é o que impede pôr aluno na turma de outra pessoa.
    turma = get_owned_or_404(db, Turma, turma_id, usuario_atual.id)
    aluno = Aluno(turma_id=turma.id, **dados.model_dump())
    db.add(aluno)
    try:
        db.commit()
    except IntegrityError as erro:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Número de chamada já usado nesta turma"
        ) from erro
    log_client.registrar_evento(
        usuario_atual.id, f"aluno_adicionado:turma:{turma.id}:aluno:{aluno.id}", ip=_ip(request)
    )
    return aluno


@router.delete(
    "/{turma_id}/alunos/{aluno_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=RESP_401 | RESP_404,
)
def remover_aluno(
    turma_id: int,
    aluno_id: int,
    request: Request,
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    turma = get_owned_or_404(db, Turma, turma_id, usuario_atual.id)
    aluno = (
        db.query(Aluno).filter(Aluno.id == aluno_id, Aluno.turma_id == turma.id).first()
    )
    if aluno is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurso não encontrado")
    db.delete(aluno)
    db.commit()
    log_client.registrar_evento(
        usuario_atual.id, f"aluno_removido:turma:{turma.id}:aluno:{aluno_id}", ip=_ip(request)
    )
