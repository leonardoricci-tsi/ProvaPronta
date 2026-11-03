import random
from pathlib import PurePath
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import UsuarioAutenticado, get_current_user, require_papel_minimo
from app.database import get_db
from app.models import Prova, Questao, Turma
from app.openapi_responses import (
    RESP_401,
    RESP_403_LIMITE_FREE,
    RESP_404,
    RESP_502_STORAGE,
    RESP_ERROS_MATERIAL,
    resp_403_papel,
)
from app.routers._ownership import get_owned_or_404
from app.schemas.prova import (
    MaterialOut,
    ProvaDetalheOut,
    ProvaIn,
    ProvaOut,
    ProvaUpdateIn,
    QuestaoIn,
)
from app.services import log_client, planos, storage

# PDF do material (livro, apostila): até 10 MB, conferido pelos bytes.
TAMANHO_MAXIMO_MATERIAL = 10 * 1024 * 1024

router = APIRouter(prefix="/provas", tags=["provas"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _montar_questoes(questoes: list[QuestaoIn]) -> list[Questao]:
    """A ordem é a posição na lista — o cliente não escolhe número."""
    return [Questao(ordem=posicao, **q.model_dump()) for posicao, q in enumerate(questoes, start=1)]


@router.get("", response_model=list[ProvaOut], responses=RESP_401)
def listar_provas(
    turma_id: int | None = Query(None, description="Só as provas desta turma"),
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Prova]:
    """Só as provas do usuário logado. O `turma_id` filtra dentro delas —
    passar o ID da turma de outra pessoa só devolve lista vazia."""
    consulta = (
        db.query(Prova)
        .options(selectinload(Prova.turma), selectinload(Prova.questoes))
        .filter(Prova.usuario_id == usuario_atual.id)
    )
    if turma_id is not None:
        consulta = consulta.filter(Prova.turma_id == turma_id)
    return consulta.order_by(Prova.criado_em.desc(), Prova.id.desc()).all()


@router.post(
    "",
    response_model=ProvaDetalheOut,
    status_code=status.HTTP_201_CREATED,
    responses=RESP_401 | RESP_403_LIMITE_FREE | RESP_404,
)
def criar_prova(
    dados: ProvaIn,
    request: Request,
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Prova:
    # A turma tem que ser do mesmo professor: a de outra pessoa dá 404,
    # como se não existisse.
    get_owned_or_404(db, Turma, dados.turma_id, usuario_atual.id)
    planos.exigir_vaga_de_prova(db, request, usuario_atual)
    prova = Prova(
        usuario_id=usuario_atual.id,
        turma_id=dados.turma_id,
        titulo=dados.titulo,
        data_aplicacao=dados.data_aplicacao,
        status=dados.status,
        questoes=_montar_questoes(dados.questoes),
    )
    db.add(prova)
    db.commit()
    log_client.registrar_evento(usuario_atual.id, f"prova_criada:{prova.id}", ip=_ip(request))
    return prova


@router.get("/{prova_id}", response_model=ProvaDetalheOut, responses=RESP_401 | RESP_404)
def detalhar_prova(
    prova_id: int,
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Prova:
    return get_owned_or_404(db, Prova, prova_id, usuario_atual.id)


@router.patch("/{prova_id}", response_model=ProvaDetalheOut, responses=RESP_401 | RESP_404)
def editar_prova(
    prova_id: int,
    dados: ProvaUpdateIn,
    request: Request,
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Prova:
    prova = get_owned_or_404(db, Prova, prova_id, usuario_atual.id)
    campos = dados.model_dump(exclude_unset=True, exclude={"questoes"})
    if "turma_id" in campos:
        get_owned_or_404(db, Turma, campos["turma_id"], usuario_atual.id)
    for campo, valor in campos.items():
        setattr(prova, campo, valor)
    if dados.questoes is not None:
        # Substitui a lista inteira: as antigas saem (delete-orphan).
        prova.questoes = _montar_questoes(dados.questoes)
    db.commit()
    log_client.registrar_evento(usuario_atual.id, f"prova_editada:{prova.id}", ip=_ip(request))
    return prova


@router.delete("/{prova_id}", status_code=status.HTTP_204_NO_CONTENT, responses=RESP_401 | RESP_404)
def remover_prova(
    prova_id: int,
    request: Request,
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    prova = get_owned_or_404(db, Prova, prova_id, usuario_atual.id)
    material_key = prova.material_key
    db.delete(prova)
    db.commit()
    # Só depois do commit: sem a prova no banco, ninguém mais acha o PDF.
    if material_key:
        storage.apagar_objeto(material_key)
    log_client.registrar_evento(usuario_atual.id, f"prova_removida:{prova_id}", ip=_ip(request))


@router.post(
    "/{prova_id}/versao-b",
    response_model=ProvaDetalheOut,
    status_code=status.HTTP_201_CREATED,
    responses=RESP_401 | resp_403_papel("professor_pro") | RESP_404,
)
def gerar_versao_b(
    prova_id: int,
    request: Request,
    usuario_atual: UsuarioAutenticado = Depends(require_papel_minimo("professor_pro")),
    db: Session = Depends(get_db),
) -> Prova:
    """Só Pro pra cima (o Free recebe 403, mesmo chamando a API direto):
    copia a prova com as questões e as alternativas em outra ordem, pra
    fileiras vizinhas não colarem. O gabarito acompanha a troca."""
    original = get_owned_or_404(db, Prova, prova_id, usuario_atual.id)
    sorteio = random.SystemRandom()
    questoes = sorteio.sample(original.questoes, k=len(original.questoes))
    copias = []
    for questao in questoes:
        ordem_alternativas = sorteio.sample(range(len(questao.alternativas)), k=len(questao.alternativas))
        copias.append(
            QuestaoIn(
                enunciado=questao.enunciado,
                alternativas=[questao.alternativas[i] for i in ordem_alternativas],
                resposta_correta=ordem_alternativas.index(questao.resposta_correta),
                assunto=questao.assunto,
            )
        )
    versao_b = Prova(
        usuario_id=usuario_atual.id,
        turma_id=original.turma_id,
        titulo=f"{original.titulo} (versão B)"[:200],
        data_aplicacao=original.data_aplicacao,
        status="rascunho",
        questoes=_montar_questoes(copias),
    )
    db.add(versao_b)
    db.commit()
    log_client.registrar_evento(
        usuario_atual.id, f"prova_versao_b:{original.id}:nova:{versao_b.id}", ip=_ip(request)
    )
    return versao_b


@router.post(
    "/{prova_id}/material",
    response_model=ProvaDetalheOut,
    responses=RESP_401 | RESP_404 | RESP_ERROS_MATERIAL | RESP_502_STORAGE,
)
def enviar_material(
    prova_id: int,
    request: Request,
    arquivo: UploadFile = File(..., description="PDF do material (livro, apostila), até 10 MB"),
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Prova:
    """Mesmo caminho da foto de perfil: o arquivo vai pro Garage (bucket
    privado), só a chave do objeto vai pro MySQL, ligada à prova."""
    prova = get_owned_or_404(db, Prova, prova_id, usuario_atual.id)
    # Lê no máximo 1 byte além do limite: o bastante pra saber que passou.
    conteudo = arquivo.file.read(TAMANHO_MAXIMO_MATERIAL + 1)
    if len(conteudo) > TAMANHO_MAXIMO_MATERIAL:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="PDF acima de 10 MB"
        )
    # Tipo conferido pela assinatura do arquivo, não pela extensão nem pelo
    # Content-Type que o navegador manda (os dois o cliente escolhe).
    if not conteudo.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Envie um arquivo PDF"
        )

    # Chave gerada pelo servidor; o nome original só serve pra exibir.
    chave_nova = f"materiais/{usuario_atual.id}/{prova.id}/{uuid4().hex}.pdf"
    nome = PurePath(arquivo.filename or "material.pdf").name[:255]
    try:
        storage.enviar_objeto(chave_nova, conteudo, "application/pdf")
    except storage.StorageUnavailable as erro:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(erro)) from erro

    chave_antiga = prova.material_key
    prova.material_key, prova.material_nome = chave_nova, nome
    try:
        db.commit()
    except Exception:
        db.rollback()
        storage.apagar_objeto(chave_nova)
        raise
    if chave_antiga:
        storage.apagar_objeto(chave_antiga)

    log_client.registrar_evento(usuario_atual.id, f"material_enviado:prova:{prova.id}", ip=_ip(request))
    return prova


@router.get("/{prova_id}/material", response_model=MaterialOut, responses=RESP_401 | RESP_404)
def abrir_material(
    prova_id: int,
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MaterialOut:
    """Link temporário (URL pré-assinada) pro PDF — só o dono da prova
    recebe. Prova sem material também dá 404."""
    prova = get_owned_or_404(db, Prova, prova_id, usuario_atual.id)
    if not prova.material_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prova sem material")
    return MaterialOut(nome=prova.material_nome or "material.pdf", url=storage.gerar_url_temporaria(prova.material_key))


@router.delete(
    "/{prova_id}/material", status_code=status.HTTP_204_NO_CONTENT, responses=RESP_401 | RESP_404
)
def remover_material(
    prova_id: int,
    request: Request,
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    prova = get_owned_or_404(db, Prova, prova_id, usuario_atual.id)
    if not prova.material_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prova sem material")
    chave = prova.material_key
    prova.material_key = prova.material_nome = None
    db.commit()
    storage.apagar_objeto(chave)
    log_client.registrar_evento(usuario_atual.id, f"material_removido:prova:{prova.id}", ip=_ip(request))
