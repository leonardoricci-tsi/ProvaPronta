"""Correção por foto (issue #8, parte 1): o professor envia a foto da folha
de respostas e recebe as respostas lidas, os acertos e a nota recomendada.

Nada é gravado ainda: a leitura é uma sugestão pro professor conferir. A
correção por foto é do plano Free (visão computacional clássica, custo quase
zero — ver o plano de negócio), então não tem `require_papel_minimo`."""

import time

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from prometheus_client import Histogram
from sqlalchemy.orm import Session

from app.auth.dependencies import UsuarioAutenticado, get_current_user
from app.database import get_db
from app.models import Aluno, Prova
from app.openapi_responses import RESP_401, RESP_404, RESP_ERROS_LEITURA
from app.routers._ownership import get_owned_or_404
from app.schemas.correcao import AlunoDaFolha, LeituraFolhaOut, RespostaLida
from app.services import leitura_folha, log_client

router = APIRouter(prefix="/provas", tags=["correção"])

# Métrica do plano de negócio: tempo de correção por folha (meta < 10 s).
TEMPO_LEITURA = Histogram(
    "provapronta_leitura_folha_segundos",
    "Tempo para ler a foto de uma folha de respostas (achar marcas, QR e bolinhas)",
    buckets=(0.25, 0.5, 1, 2, 3, 5, 10),
)


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _422(detalhe: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detalhe)


@router.post(
    "/{prova_id}/correcao/leitura",
    response_model=LeituraFolhaOut,
    responses=RESP_401 | RESP_404 | RESP_ERROS_LEITURA,
)
def ler_folha(
    prova_id: int,
    request: Request,
    foto: UploadFile = File(description="Foto da folha de respostas (JPEG, PNG ou WebP, até 10 MB)"),
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeituraFolhaOut:
    """Lê a foto de uma folha: acha as 4 marcas, endireita, lê o QR (que diz
    o aluno e precisa ser desta prova) e as bolinhas, e compara com o
    gabarito. Rota síncrona de propósito: o OpenCV roda no threadpool."""
    prova = get_owned_or_404(db, Prova, prova_id, usuario_atual.id)
    if not prova.questoes:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A prova ainda não tem questões")

    conteudo = foto.file.read(leitura_folha.TAMANHO_MAXIMO_BYTES + 1)
    inicio = time.perf_counter()
    try:
        leitura = leitura_folha.ler_folha(conteudo, [len(q.alternativas) for q in prova.questoes])
    except leitura_folha.ImagemGrandeDemais:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Foto acima de 10 MB")
    except leitura_folha.ImagemInvalida:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Envie uma foto (JPEG, PNG ou WebP)"
        )
    except leitura_folha.FolhaNaoEncontrada:
        raise _422(
            "Não encontrei as 4 marcas pretas dos cantos. Fotografe a folha inteira, de cima, sem cortar os cantos"
        )
    except leitura_folha.QrIlegivel:
        raise _422(
            "Não consegui ler o QR code da folha. Tire outra foto com mais luz e foco; se a folha foi "
            "impressa antes da correção por foto, imprima de novo"
        )
    finally:
        TEMPO_LEITURA.observe(time.perf_counter() - inicio)

    if leitura.prova_id != prova.id:
        raise _422(f"Esta folha é da prova {leitura.prova_id}, não desta")
    aluno = db.get(Aluno, leitura.aluno_id)
    if aluno is None or aluno.turma_id != prova.turma_id:
        raise _422("O aluno desta folha não está mais na turma")

    respostas = [
        RespostaLida(
            numero=numero,
            questao_id=questao.id,
            marcada=lida.marcada,
            situacao=lida.situacao,
            correta=questao.resposta_correta,
            acertou=lida.marcada == questao.resposta_correta,
            preenchimento=lida.preenchimento,
        )
        for numero, (questao, lida) in enumerate(zip(prova.questoes, leitura.questoes), start=1)
    ]
    acertos = sum(r.acertou for r in respostas)
    total = len(respostas)
    log_client.registrar_evento(
        usuario_atual.id, f"folha_lida:prova:{prova.id}:aluno:{aluno.id}:{acertos}/{total}", ip=_ip(request)
    )
    return LeituraFolhaOut(
        prova_id=prova.id,
        aluno=AlunoDaFolha(id=aluno.id, nome=aluno.nome, numero_chamada=aluno.numero_chamada),
        respostas=respostas,
        acertos=acertos,
        total=total,
        nota_recomendada=round(acertos / total * 10, 1),
        conferir=[r.numero for r in respostas if r.situacao != "ok"],
    )
