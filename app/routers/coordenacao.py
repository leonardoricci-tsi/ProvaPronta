from collections import Counter, defaultdict

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import UsuarioAutenticado, require_papel_minimo
from app.database import get_db
from app.models import Prova, Turma
from app.openapi_responses import RESP_401, resp_403_papel
from app.schemas.coordenacao import (
    AssuntoRelatorioOut,
    ProvasPorStatusOut,
    RelatorioCoordenacaoOut,
    TotaisRelatorioOut,
    TurmaRelatorioOut,
)
from app.services import log_client

SEM_ASSUNTO = "Sem assunto"

router = APIRouter(prefix="/coordenacao", tags=["coordenacao"])


@router.get(
    "/relatorio",
    response_model=RelatorioCoordenacaoOut,
    responses=RESP_401 | resp_403_papel("coordenador"),
)
def relatorio(
    request: Request,
    usuario_atual: UsuarioAutenticado = Depends(require_papel_minimo("coordenador")),
    db: Session = Depends(get_db),
) -> RelatorioCoordenacaoOut:
    """Relatório do plano Escola: por turma (alunos, provas por status,
    questões) e por assunto (quantas questões cobrem cada um — onde a
    avaliação está concentrada e o que ficou de fora). Professor e Pro
    recebem 403. Só os dados do próprio usuário, como no resto da API."""
    turmas = (
        db.query(Turma)
        .options(selectinload(Turma.alunos))
        .filter(Turma.usuario_id == usuario_atual.id)
        .order_by(Turma.ano_letivo.desc(), Turma.nome)
        .all()
    )
    provas = (
        db.query(Prova)
        .options(selectinload(Prova.questoes))
        .filter(Prova.usuario_id == usuario_atual.id)
        .all()
    )

    provas_por_turma: dict[int, list[Prova]] = defaultdict(list)
    questoes_por_assunto: Counter[str] = Counter()
    provas_por_assunto: dict[str, set[int]] = defaultdict(set)
    for prova in provas:
        provas_por_turma[prova.turma_id].append(prova)
        for questao in prova.questoes:
            assunto = (questao.assunto or "").strip() or SEM_ASSUNTO
            questoes_por_assunto[assunto] += 1
            provas_por_assunto[assunto].add(prova.id)

    linhas_turma = []
    for turma in turmas:
        da_turma = provas_por_turma[turma.id]
        por_status = Counter(p.status for p in da_turma)
        linhas_turma.append(
            TurmaRelatorioOut(
                id=turma.id,
                nome=turma.nome,
                disciplina=turma.disciplina,
                ano_letivo=turma.ano_letivo,
                total_alunos=turma.total_alunos,
                provas=ProvasPorStatusOut(**por_status),
                total_questoes=sum(p.total_questoes for p in da_turma),
            )
        )

    # Mais questões primeiro; empate em ordem alfabética.
    assuntos = [
        AssuntoRelatorioOut(assunto=assunto, questoes=total, provas=len(provas_por_assunto[assunto]))
        for assunto, total in sorted(questoes_por_assunto.items(), key=lambda par: (-par[1], par[0]))
    ]

    log_client.registrar_evento(
        usuario_atual.id,
        "relatorio_coordenacao_consultado",
        ip=request.client.host if request.client else None,
    )
    return RelatorioCoordenacaoOut(
        totais=TotaisRelatorioOut(
            turmas=len(turmas),
            alunos=sum(t.total_alunos for t in turmas),
            provas=len(provas),
            provas_aprovadas=sum(1 for p in provas if p.status == "aprovada"),
            questoes=sum(p.total_questoes for p in provas),
        ),
        turmas=linhas_turma,
        assuntos=assuntos,
    )
