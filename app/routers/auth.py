from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials

from app.auth.dependencies import UsuarioAutenticado, bearer_scheme, get_current_user
from app.openapi_responses import RESP_401, RESP_403_ADMIN, RESP_502_AUTH_SERVICE
from app.schemas.auth import LoginIn, RegisterIn
from app.schemas.password_reset import ForgotPasswordIn, ResetPasswordIn
from app.services import log_client
from app.services.auth_client import AuthServiceUnavailable, forward

router = APIRouter(prefix="/auth", tags=["auth"])

# Rotas /auth/* (exceto /logout) são proxy puro pro auth-service: o corpo
# de erro que o cliente recebe é o que o auth-service mandou, repassado tal
# e qual — os exemplos abaixo documentam o que ele de fato devolve hoje.
_RESP_EMAIL_DUPLICADO = {
    400: {
        "description": "E-mail já cadastrado",
        "content": {"application/json": {"example": {"detail": "Email já cadastrado"}}},
    }
}
_RESP_LOGIN_INVALIDO = {
    401: {
        "description": "E-mail ou senha não batem com nenhum usuário cadastrado",
        "content": {"application/json": {"example": {"detail": "Email ou senha inválidos"}}},
    }
}
_RESP_LINK_INVALIDO = {
    400: {
        "description": "Token de redefinição inexistente, expirado ou já usado",
        "content": {
            "application/json": {"example": {"detail": "Link inválido, expirado ou já utilizado"}}
        },
    }
}
_RESP_PAPEL_INVALIDO_OU_USUARIO_NAO_ENCONTRADO = {
    400: {
        "description": "`role` enviado não é um dos papéis válidos",
        "content": {
            "application/json": {
                "example": {
                    "detail": "Papel inválido. Use um de: professor, professor_pro, coordenador, admin"
                }
            }
        },
    },
    404: {
        "description": "usuario_id não existe no auth-service",
        "content": {"application/json": {"example": {"detail": "Usuário não encontrado"}}},
    },
}


def _proxy(response) -> JSONResponse:
    return JSONResponse(status_code=response.status_code, content=response.json())


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    responses=_RESP_EMAIL_DUPLICADO | RESP_502_AUTH_SERVICE,
)
def register(dados: RegisterIn) -> JSONResponse:
    try:
        resposta = forward("POST", "/auth/register", json=dados.model_dump())
    except AuthServiceUnavailable as erro:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(erro)) from erro
    return _proxy(resposta)


@router.post("/login", responses=_RESP_LOGIN_INVALIDO | RESP_502_AUTH_SERVICE)
def login(dados: LoginIn) -> JSONResponse:
    try:
        resposta = forward("POST", "/auth/login", json=dados.model_dump())
    except AuthServiceUnavailable as erro:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(erro)) from erro
    return _proxy(resposta)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, responses=RESP_401)
def logout(
    request: Request,
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
) -> None:
    """JWT é stateless — não existe sessão pra invalidar no servidor (quem
    descarta o token é o front). Essa rota não faz mais nada além de
    registrar o evento de auditoria: "logout" é um dos eventos mínimos
    exigidos pela atividade 5, e sem uma rota pra chamar antes de descartar
    o token, esse evento nunca aconteceria."""
    log_client.registrar_evento(
        usuario_atual.id, "logout", ip=request.client.host if request.client else None
    )


@router.post("/refresh", responses=RESP_401 | RESP_502_AUTH_SERVICE)
def refresh(authorization: str | None = Header(None)) -> JSONResponse:
    """Token novo com o papel atual (atividade 7): depois que um plano pago
    troca o papel, o token antigo ainda carrega o papel velho."""
    headers = {"Authorization": authorization} if authorization else {}
    try:
        resposta = forward("POST", "/auth/refresh", headers=headers)
    except AuthServiceUnavailable as erro:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(erro)) from erro
    return _proxy(resposta)


@router.get("/me", responses=RESP_401 | RESP_502_AUTH_SERVICE)
def me(authorization: str | None = Header(None)) -> JSONResponse:
    headers = {"Authorization": authorization} if authorization else {}
    try:
        resposta = forward("GET", "/auth/me", headers=headers)
    except AuthServiceUnavailable as erro:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(erro)) from erro
    return _proxy(resposta)


@router.post("/forgot-password", responses=RESP_502_AUTH_SERVICE)
def forgot_password(dados: ForgotPasswordIn) -> JSONResponse:
    try:
        resposta = forward("POST", "/auth/forgot-password", json=dados.model_dump())
    except AuthServiceUnavailable as erro:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(erro)) from erro
    return _proxy(resposta)


@router.post("/reset-password", responses=_RESP_LINK_INVALIDO | RESP_502_AUTH_SERVICE)
def reset_password(dados: ResetPasswordIn) -> JSONResponse:
    try:
        resposta = forward("POST", "/auth/reset-password", json=dados.model_dump())
    except AuthServiceUnavailable as erro:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(erro)) from erro
    return _proxy(resposta)


def _bearer_header(credentials: HTTPAuthorizationCredentials | None) -> dict:
    return {"Authorization": f"Bearer {credentials.credentials}"} if credentials else {}


@router.get("/admin/users", responses=RESP_401 | RESP_403_ADMIN | RESP_502_AUTH_SERVICE)
def listar_usuarios(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> JSONResponse:
    """Proxy pro auth-service — só ele tem a tabela `usuarios`, então quem
    decide se o chamador é admin (403 se não for) é o auth-service, não o
    catálogo (`auth-service/app/routers/admin.py`).

    Usa `Depends(bearer_scheme)` (não `Header(None)` cru) só pra registrar
    esse endpoint como protegido no OpenAPI — assim o botão "Authorize" do
    Swagger funciona aqui também, igual no resto da API."""
    try:
        resposta = forward("GET", "/auth/admin/users", headers=_bearer_header(credentials))
    except AuthServiceUnavailable as erro:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(erro)) from erro
    return _proxy(resposta)


@router.patch(
    "/admin/users/{usuario_id}/role",
    responses=RESP_401
    | RESP_403_ADMIN
    | RESP_502_AUTH_SERVICE
    | _RESP_PAPEL_INVALIDO_OU_USUARIO_NAO_ENCONTRADO,
)
def alterar_papel_usuario(
    usuario_id: int,
    dados: dict = Body(...),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> JSONResponse:
    try:
        resposta = forward(
            "PATCH",
            f"/auth/admin/users/{usuario_id}/role",
            json=dados,
            headers=_bearer_header(credentials),
        )
    except AuthServiceUnavailable as erro:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(erro)) from erro
    return _proxy(resposta)
