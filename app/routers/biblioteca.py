from pathlib import PurePath
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import UsuarioAutenticado, get_current_user
from app.database import get_db
from app.models import Material, Pasta
from app.openapi_responses import (
    RESP_401,
    RESP_403_LIMITE_FREE,
    RESP_404,
    RESP_502_STORAGE,
    RESP_ERROS_MATERIAL,
)
from app.routers._ownership import get_owned_or_404
from app.schemas.biblioteca import LinkMaterialOut, MaterialOut, PastaIn, PastaOut
from app.services import log_client, pdf, planos, storage

# Quantos PDFs dá pra mandar numa tacada só (o corpo inteiro fica em
# memória: 10 × 10 MB no pior caso).
MAX_ARQUIVOS_POR_ENVIO = 10

router = APIRouter(tags=["biblioteca"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/pastas", response_model=list[PastaOut], responses=RESP_401)
def listar_pastas(
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Pasta]:
    """Só as pastas do usuário logado, com os PDFs de cada uma."""
    return (
        db.query(Pasta)
        .options(selectinload(Pasta.materiais))
        .filter(Pasta.usuario_id == usuario_atual.id)
        .order_by(Pasta.nome)
        .all()
    )


@router.post("/pastas", response_model=PastaOut, status_code=status.HTTP_201_CREATED, responses=RESP_401)
def criar_pasta(
    dados: PastaIn,
    request: Request,
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Pasta:
    pasta = Pasta(usuario_id=usuario_atual.id, nome=dados.nome.strip())
    db.add(pasta)
    db.commit()
    log_client.registrar_evento(usuario_atual.id, f"pasta_criada:{pasta.id}", ip=_ip(request))
    return pasta


@router.get("/pastas/{pasta_id}", response_model=PastaOut, responses=RESP_401 | RESP_404)
def detalhar_pasta(
    pasta_id: int,
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Pasta:
    return get_owned_or_404(db, Pasta, pasta_id, usuario_atual.id)


@router.patch("/pastas/{pasta_id}", response_model=PastaOut, responses=RESP_401 | RESP_404)
def renomear_pasta(
    pasta_id: int,
    dados: PastaIn,
    request: Request,
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Pasta:
    pasta = get_owned_or_404(db, Pasta, pasta_id, usuario_atual.id)
    pasta.nome = dados.nome.strip()
    db.commit()
    log_client.registrar_evento(usuario_atual.id, f"pasta_renomeada:{pasta.id}", ip=_ip(request))
    return pasta


@router.delete("/pastas/{pasta_id}", status_code=status.HTTP_204_NO_CONTENT, responses=RESP_401 | RESP_404)
def remover_pasta(
    pasta_id: int,
    request: Request,
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Leva os PDFs junto (no banco, CASCADE; no Garage, depois do commit)."""
    pasta = get_owned_or_404(db, Pasta, pasta_id, usuario_atual.id)
    chaves = [material.chave for material in pasta.materiais]
    db.delete(pasta)
    db.commit()
    for chave in chaves:
        storage.apagar_objeto(chave)
    log_client.registrar_evento(usuario_atual.id, f"pasta_removida:{pasta_id}", ip=_ip(request))


@router.post(
    "/pastas/{pasta_id}/materiais",
    response_model=list[MaterialOut],
    status_code=status.HTTP_201_CREATED,
    responses=RESP_401 | RESP_403_LIMITE_FREE | RESP_404 | RESP_ERROS_MATERIAL | RESP_502_STORAGE,
)
def enviar_materiais(
    pasta_id: int,
    request: Request,
    arquivos: list[UploadFile] = File(..., description="Um ou mais PDFs, até 10 MB cada"),
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Material]:
    """Envia um ou vários PDFs pra pasta. Tudo ou nada: se um arquivo não
    for PDF ou passar do tamanho, nenhum é gravado."""
    pasta = get_owned_or_404(db, Pasta, pasta_id, usuario_atual.id)
    if len(arquivos) > MAX_ARQUIVOS_POR_ENVIO:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Envie no máximo {MAX_ARQUIVOS_POR_ENVIO} PDFs por vez",
        )
    planos.exigir_vaga_de_materiais(db, request, usuario_atual, novos=len(arquivos))
    # Valida todos antes de gravar qualquer um.
    lidos = [(arquivo, pdf.ler_pdf_enviado(arquivo)) for arquivo in arquivos]

    enviados: list[str] = []
    materiais = []
    try:
        for arquivo, conteudo in lidos:
            chave = f"biblioteca/{usuario_atual.id}/{pasta.id}/{uuid4().hex}.pdf"
            storage.enviar_objeto(chave, conteudo, "application/pdf")
            enviados.append(chave)
            materiais.append(
                Material(
                    usuario_id=usuario_atual.id,
                    pasta_id=pasta.id,
                    nome=PurePath(arquivo.filename or "material.pdf").name[:255],
                    chave=chave,
                    tamanho_bytes=len(conteudo),
                )
            )
        db.add_all(materiais)
        db.commit()
    except storage.StorageUnavailable as erro:
        db.rollback()
        for chave in enviados:
            storage.apagar_objeto(chave)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(erro)) from erro
    except Exception:
        db.rollback()
        for chave in enviados:
            storage.apagar_objeto(chave)
        raise

    log_client.registrar_evento(
        usuario_atual.id, f"materiais_enviados:pasta:{pasta.id}:{len(materiais)}", ip=_ip(request)
    )
    return materiais


@router.get("/materiais/{material_id}/link", response_model=LinkMaterialOut, responses=RESP_401 | RESP_404)
def abrir_material(
    material_id: int,
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LinkMaterialOut:
    """Link temporário (URL pré-assinada) pro PDF — só o dono recebe."""
    material = get_owned_or_404(db, Material, material_id, usuario_atual.id)
    return LinkMaterialOut(nome=material.nome, url=storage.gerar_url_temporaria(material.chave))


@router.delete(
    "/materiais/{material_id}", status_code=status.HTTP_204_NO_CONTENT, responses=RESP_401 | RESP_404
)
def remover_material(
    material_id: int,
    request: Request,
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    material = get_owned_or_404(db, Material, material_id, usuario_atual.id)
    chave = material.chave
    db.delete(material)
    db.commit()
    storage.apagar_objeto(chave)
    log_client.registrar_evento(usuario_atual.id, f"material_removido:{material_id}", ip=_ip(request))
