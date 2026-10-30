from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.auth.dependencies import UsuarioAutenticado, bearer_scheme, get_current_user
from app.database import get_db
from app.models import Perfil
from app.openapi_responses import (
    RESP_401,
    RESP_403_PERFIL_ALHEIO,
    RESP_404_USUARIO,
    RESP_502_AUTH_SERVICE,
    RESP_502_STORAGE,
    RESP_ERROS_FOTO,
)
from app.routers.premium import plano_pago
from app.schemas.profile import PerfilOut, PerfilUpdateIn
from app.services import log_client, storage
from app.services.imagem import (
    TAMANHO_MAXIMO_BYTES,
    ImagemGrandeDemais,
    ImagemInvalida,
    processar_foto,
)
from app.services.auth_client import AuthServiceUnavailable, forward

router = APIRouter(prefix="/profiles", tags=["profiles"])


def require_dono_do_perfil(
    usuario_id: int,
    request: Request,
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
) -> UsuarioAutenticado:
    """Só o dono edita o próprio perfil (atividade 6, reaproveitando a
    atividade 4): compara o `usuario_id` da URL com o `sub` do JWT — nunca
    com nada que venha no corpo. Nem admin passa: dar suporte é uma
    coisa, reescrever a bio de alguém é outra.

    A tentativa negada vai pro log de auditoria (atividade 5), igual às
    negações de `require_admin`/`require_papel_minimo`."""
    if usuario_id != usuario_atual.id:
        log_client.registrar_evento(
            usuario_atual.id,
            f"acesso_negado:perfil:{usuario_id}",
            ip=request.client.host if request.client else None,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Você só pode editar o próprio perfil"
        )
    return usuario_atual


def _buscar_nome(usuario_id: int, credentials: HTTPAuthorizationCredentials | None) -> str:
    """O nome mora na tabela `usuarios`, do auth-service — o catálogo só
    tem bio/foto. Repassa o mesmo token de quem está vendo o perfil."""
    headers = {"Authorization": f"Bearer {credentials.credentials}"} if credentials else {}
    try:
        resposta = forward("GET", f"/auth/users/{usuario_id}", headers=headers)
    except AuthServiceUnavailable as erro:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(erro)) from erro
    if resposta.status_code == status.HTTP_404_NOT_FOUND:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    if resposta.status_code != status.HTTP_200_OK:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Serviço de autenticação indisponível no momento",
        )
    return resposta.json()["nome"]


def _montar_perfil(
    usuario_id: int,
    usuario_atual: UsuarioAutenticado,
    credentials: HTTPAuthorizationCredentials | None,
    db: Session,
) -> PerfilOut:
    nome = _buscar_nome(usuario_id, credentials)
    # Quem nunca editou o perfil não tem linha em `perfis` — mostra vazio,
    # não 404: o usuário existe (o auth-service acabou de confirmar).
    perfil = db.get(Perfil, usuario_id)
    foto_key = perfil.foto_key if perfil else None
    return PerfilOut(
        usuario_id=usuario_id,
        nome=nome,
        bio=(perfil.bio if perfil else None) or "",
        foto_url=storage.gerar_url_temporaria(foto_key) if foto_key else None,
        eh_meu=usuario_id == usuario_atual.id,
        plano=plano_pago(db, usuario_id),
    )


@router.get(
    "/{usuario_id}",
    response_model=PerfilOut,
    responses=RESP_401 | RESP_404_USUARIO | RESP_502_AUTH_SERVICE,
)
def ver_perfil(
    usuario_id: int,
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> PerfilOut:
    """Qualquer usuário logado vê o perfil de qualquer outro — é rede
    social. Editar é que é só do dono (PATCH abaixo)."""
    return _montar_perfil(usuario_id, usuario_atual, credentials, db)


@router.patch(
    "/{usuario_id}",
    response_model=PerfilOut,
    responses=RESP_401 | RESP_403_PERFIL_ALHEIO | RESP_404_USUARIO | RESP_502_AUTH_SERVICE,
)
def editar_perfil(
    usuario_id: int,
    dados: PerfilUpdateIn,
    request: Request,
    usuario_atual: UsuarioAutenticado = Depends(require_dono_do_perfil),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> PerfilOut:
    perfil = db.get(Perfil, usuario_atual.id)
    if perfil is None:
        perfil = Perfil(usuario_id=usuario_atual.id)
        db.add(perfil)
    perfil.bio = dados.bio
    db.commit()
    log_client.registrar_evento(
        usuario_atual.id,
        "atualizar_perfil",
        ip=request.client.host if request.client else None,
    )
    return _montar_perfil(usuario_atual.id, usuario_atual, credentials, db)


@router.post(
    "/{usuario_id}/foto",
    response_model=PerfilOut,
    responses=RESP_401
    | RESP_403_PERFIL_ALHEIO
    | RESP_ERROS_FOTO
    | RESP_404_USUARIO
    | RESP_502_AUTH_SERVICE
    | RESP_502_STORAGE,
)
def enviar_foto(
    usuario_id: int,
    request: Request,
    arquivo: UploadFile = File(..., description="JPEG, PNG ou WEBP, até 2 MB"),
    usuario_atual: UsuarioAutenticado = Depends(require_dono_do_perfil),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> PerfilOut:
    """Uma ação de upload, duas gravações separadas: o arquivo vai pro
    Garage, só a chave do objeto vai pro MySQL."""
    # Lê no máximo 1 byte além do limite — o suficiente pra saber que
    # passou, sem carregar um arquivo de 1 GB inteiro na memória.
    try:
        conteudo, extensao, content_type = processar_foto(
            arquivo.file.read(TAMANHO_MAXIMO_BYTES + 1)
        )
    except ImagemGrandeDemais as erro:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Imagem acima de 2 MB"
        ) from erro
    except ImagemInvalida as erro:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Envie uma imagem JPEG, PNG ou WEBP",
        ) from erro

    # Chave gerada pelo servidor (nunca o nome de arquivo do cliente); o
    # uuid novo a cada upload evita que o navegador mostre a foto antiga
    # do cache e que dois uploads seguidos se sobrescrevam.
    chave_nova = f"perfis/{usuario_atual.id}/{uuid4().hex}.{extensao}"
    try:
        storage.enviar_objeto(chave_nova, conteudo, content_type)
    except storage.StorageUnavailable as erro:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(erro)) from erro

    perfil = db.get(Perfil, usuario_atual.id)
    if perfil is None:
        perfil = Perfil(usuario_id=usuario_atual.id)
        db.add(perfil)
    chave_antiga = perfil.foto_key
    perfil.foto_key = chave_nova
    try:
        db.commit()
    except Exception:
        # O arquivo já subiu mas o banco não registrou: sem a chave no
        # banco, ninguém nunca mais acha esse objeto — apaga pra não virar lixo.
        db.rollback()
        storage.apagar_objeto(chave_nova)
        raise

    # Só depois do commit: se o banco tivesse falhado, a foto antiga ainda
    # seria a referenciada e não podia sumir.
    if chave_antiga:
        storage.apagar_objeto(chave_antiga)

    log_client.registrar_evento(
        usuario_atual.id,
        "upload_foto_perfil",
        ip=request.client.host if request.client else None,
    )
    return _montar_perfil(usuario_atual.id, usuario_atual, credentials, db)
