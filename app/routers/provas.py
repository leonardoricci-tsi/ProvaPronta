import random
from pathlib import PurePath
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import UsuarioAutenticado, get_current_user, require_papel_minimo
from app.database import get_db
from app.models import Material, Pasta, Prova, Questao, Turma
from app.openapi_responses import (
    RESP_401,
    RESP_403_LIMITE_FREE,
    RESP_404,
    RESP_409_APROVACAO,
    RESP_409_FOLHAS,
    RESP_502_STORAGE,
    RESP_ERROS_GERACAO,
    RESP_ERROS_MATERIAL,
    resp_403_papel,
)
from app.routers._ownership import get_owned_or_404
from app.schemas.prova import (
    GerarQuestoesIn,
    GerarQuestoesOut,
    MaterialOut,
    ProvaDetalheOut,
    ProvaIn,
    ProvaOut,
    ProvaUpdateIn,
    QuestaoIn,
)
from app.services import folha_resposta, gerador_questoes, log_client, pdf, planos, storage

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
    # A aprovação vale pra prova como a coordenação viu: mexeu, perdeu.
    # Volta pra "pronta" (ou pro status que o professor mandou) e precisa
    # ser aprovada de novo.
    if prova.status == "aprovada" and (campos or dados.questoes is not None):
        prova.status = "pronta"
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


# Teto de PDFs numa geração: cada um é baixado do Garage e lido em memória.
MAX_PDFS_POR_GERACAO = 10


def _fontes_da_geracao(
    db: Session, prova: Prova, dados: GerarQuestoesIn, usuario_id: int
) -> list[tuple[str, str]]:
    """(nome, chave no Garage) dos PDFs escolhidos, sem repetir. Tudo
    filtrado pelo dono na query: id de pasta ou PDF de outra pessoa conta
    como inexistente (404)."""
    escolheu_biblioteca = bool(dados.pasta_ids or dados.material_ids)
    fontes: dict[str, str] = {}
    if dados.usar_pdf_da_prova or not escolheu_biblioteca:
        if prova.material_key:
            fontes[prova.material_key] = prova.material_nome or "material.pdf"
        elif not escolheu_biblioteca:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Anexe o PDF da apostila ou escolha PDFs da biblioteca antes de gerar questões",
            )

    if dados.pasta_ids:
        pastas = (
            db.query(Pasta)
            .options(selectinload(Pasta.materiais))
            .filter(Pasta.id.in_(dados.pasta_ids), Pasta.usuario_id == usuario_id)
            .all()
        )
        if len(pastas) != len(set(dados.pasta_ids)):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pasta não encontrada")
        for pasta in pastas:
            for material in pasta.materiais:
                fontes.setdefault(material.chave, material.nome)
    if dados.material_ids:
        materiais = (
            db.query(Material)
            .filter(Material.id.in_(dados.material_ids), Material.usuario_id == usuario_id)
            .order_by(Material.nome)
            .all()
        )
        if len(materiais) != len(set(dados.material_ids)):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF não encontrado")
        for material in materiais:
            fontes.setdefault(material.chave, material.nome)

    if not fontes:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="As pastas escolhidas não têm nenhum PDF"
        )
    if len(fontes) > MAX_PDFS_POR_GERACAO:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Escolha no máximo {MAX_PDFS_POR_GERACAO} PDFs por geração",
        )
    return [(nome, chave) for chave, nome in fontes.items()]


@router.post(
    "/{prova_id}/gerar-questoes",
    response_model=GerarQuestoesOut,
    responses=RESP_401 | resp_403_papel("professor_pro") | RESP_404 | RESP_ERROS_GERACAO,
)
def gerar_questoes_do_pdf(
    prova_id: int,
    request: Request,
    dados: GerarQuestoesIn | None = None,
    usuario_atual: UsuarioAutenticado = Depends(require_papel_minimo("professor_pro")),
    db: Session = Depends(get_db),
) -> GerarQuestoesOut:
    """Plano Pro: lê os PDFs escolhidos — pastas inteiras e/ou PDFs da
    biblioteca, e/ou o PDF anexado à prova — e pede à IA questões de
    múltipla escolha com gabarito. Devolve **sugestões**: nada é gravado; o
    professor revisa no editor e salva. Free recebe 403. Pasta ou PDF de
    outra pessoa dá 404, como se não existisse."""
    dados = dados or GerarQuestoesIn()
    prova = get_owned_or_404(db, Prova, prova_id, usuario_atual.id)
    fontes = _fontes_da_geracao(db, prova, dados, usuario_atual.id)
    # Falha de serviço de fora (Garage, IA) responde 503, não 502: o
    # Cloudflare na frente do site troca todo 502 da origem pela página de
    # erro dele, e a mensagem pro professor se perderia.
    try:
        arquivos = [(nome, storage.baixar_objeto(chave)) for nome, chave in fontes]
    except storage.StorageUnavailable as erro:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(erro)) from erro
    try:
        texto = gerador_questoes.extrair_texto_de_varios(arquivos)
        questoes = gerador_questoes.gerar_questoes(texto, dados.quantidade, prova.turma.disciplina)
    except gerador_questoes.PdfSemTexto as erro:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(erro)) from erro
    except gerador_questoes.GeracaoIndisponivel as erro:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(erro)) from erro
    except gerador_questoes.FalhaNaGeracao as erro:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(erro)) from erro

    log_client.registrar_evento(
        usuario_atual.id,
        f"questoes_geradas:prova:{prova.id}:{len(questoes)}:pdfs:{len(fontes)}",
        ip=_ip(request),
    )
    nomes = [nome for nome, _ in fontes]
    return GerarQuestoesOut(
        questoes=questoes,
        fonte=nomes[0] if len(nomes) == 1 else f"{len(nomes)} PDFs",
        fontes=nomes,
    )


def _resposta_pdf(conteudo: bytes, nome_arquivo: str) -> Response:
    # inline: abre no visualizador do navegador (de onde dá pra imprimir).
    return Response(
        content=conteudo,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{nome_arquivo}"'},
    )


def _data_br(prova: Prova) -> str | None:
    return prova.data_aplicacao.strftime("%d/%m/%Y") if prova.data_aplicacao else None


_RESP_PDF = {200: {"content": {"application/pdf": {}}, "description": "PDF pronto para imprimir"}}


@router.get(
    "/{prova_id}/folhas-resposta.pdf",
    response_class=Response,
    responses=_RESP_PDF | RESP_401 | RESP_404 | RESP_409_FOLHAS,
)
def folhas_de_resposta(
    prova_id: int,
    request: Request,
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Uma folha por aluno da turma: QR code (prova + aluno), grade de
    bolinhas A–E por questão e marcas nos cantos pra correção por foto."""
    prova = get_owned_or_404(db, Prova, prova_id, usuario_atual.id)
    if not prova.questoes:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A prova ainda não tem questões")
    alunos = prova.turma.alunos
    if not alunos:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cadastre os alunos da turma antes de imprimir as folhas de resposta",
        )
    turma = f"{prova.turma.nome} — {prova.turma.disciplina}"
    alternativas = [len(q.alternativas) for q in prova.questoes]
    conteudo = folha_resposta.gerar_folhas(
        [
            folha_resposta.DadosFolha(
                prova_id=prova.id,
                titulo=prova.titulo,
                turma=turma,
                data_aplicacao=_data_br(prova),
                aluno_id=aluno.id,
                aluno_nome=aluno.nome,
                numero_chamada=aluno.numero_chamada,
                alternativas_por_questao=alternativas,
            )
            for aluno in alunos
        ]
    )
    log_client.registrar_evento(
        usuario_atual.id, f"folhas_geradas:prova:{prova.id}:{len(alunos)}", ip=_ip(request)
    )
    return _resposta_pdf(conteudo, f"folhas-resposta-prova-{prova.id}.pdf")


@router.get(
    "/{prova_id}/caderno.pdf",
    response_class=Response,
    responses=_RESP_PDF | RESP_401 | RESP_404 | RESP_409_FOLHAS,
)
def caderno_da_prova(
    prova_id: int,
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """O caderno com as questões pra imprimir — sem o gabarito."""
    prova = get_owned_or_404(db, Prova, prova_id, usuario_atual.id)
    if not prova.questoes:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A prova ainda não tem questões")
    conteudo = folha_resposta.gerar_caderno(
        prova.titulo,
        f"{prova.turma.nome} — {prova.turma.disciplina}",
        _data_br(prova),
        [folha_resposta.QuestaoCaderno(q.enunciado, list(q.alternativas)) for q in prova.questoes],
    )
    return _resposta_pdf(conteudo, f"caderno-prova-{prova.id}.pdf")


@router.post(
    "/{prova_id}/aprovar",
    response_model=ProvaDetalheOut,
    responses=RESP_401 | resp_403_papel("coordenador") | RESP_404 | RESP_409_APROVACAO,
)
def aprovar_prova(
    prova_id: int,
    request: Request,
    usuario_atual: UsuarioAutenticado = Depends(require_papel_minimo("coordenador")),
    db: Session = Depends(get_db),
) -> Prova:
    """Só a coordenação (plano Escola) aprova: professor e Pro recebem 403,
    mesmo chamando a API direto. Só prova "pronta" pode ser aprovada — um
    rascunho ainda está sendo escrito."""
    prova = get_owned_or_404(db, Prova, prova_id, usuario_atual.id)
    if prova.status != "pronta":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Só prova pronta pode ser aprovada"
            if prova.status == "rascunho"
            else "A prova já está aprovada",
        )
    prova.status = "aprovada"
    db.commit()
    log_client.registrar_evento(usuario_atual.id, f"prova_aprovada:{prova.id}", ip=_ip(request))
    return prova


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
    conteudo = pdf.ler_pdf_enviado(arquivo)

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
