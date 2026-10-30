from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.security import decode_access_token
from app.services import log_client

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class UsuarioAutenticado:
    """Identidade extraída do JWT — o catálogo não tem mais a tabela
    `usuarios` (ela é do auth-service agora), então não há um model
    SQLAlchemy aqui: só o que o token já carrega."""

    id: int
    role: str
    nome: str


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> UsuarioAutenticado:
    credenciais_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas ou expiradas",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credenciais_invalidas

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise credenciais_invalidas

    try:
        usuario_id = int(payload["sub"])
        role = payload["role"]
    except (KeyError, ValueError, TypeError) as erro:
        raise credenciais_invalidas from erro

    # .get com fallback: tokens emitidos antes do claim `nome` existir ainda
    # circulam até expirar (JWT_EXPIRE_MINUTES) — não podem virar 401 por isso.
    nome = payload.get("nome") or ""

    return UsuarioAutenticado(id=usuario_id, role=role, nome=nome)


def require_admin(
    request: Request,
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
) -> UsuarioAutenticado:
    if usuario_atual.role != "admin":
        # Tentativa negada por permissão (atividade 5): especialmente
        # valiosa pra auditoria de segurança, por isso loga aqui — cobre
        # toda rota que usa essa dependência, não só uma por uma.
        log_client.registrar_evento(
            usuario_atual.id,
            "acesso_negado:admin",
            ip=request.client.host if request.client else None,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito a admins")
    return usuario_atual


# Escada de papéis — cada um inclui a permissão do anterior. "admin" é o
# topo: faz tudo que os outros fazem e ainda opera o sistema
# (require_admin acima cobre as ações exclusivas dele: ver o log de
# auditoria, promover usuário) — não é um papel à parte.
NIVEL_PAPEL = {"professor": 1, "professor_pro": 2, "coordenador": 3, "admin": 4}


def require_papel_minimo(papel_minimo: str):
    """Fábrica de dependência: recusa com 403 quem tiver um papel de nível
    abaixo do exigido. O nível vem do claim `role` do JWT — nunca de nada
    que o cliente possa mandar na requisição."""
    nivel_exigido = NIVEL_PAPEL[papel_minimo]

    def dependencia(
        request: Request,
        usuario_atual: UsuarioAutenticado = Depends(get_current_user),
    ) -> UsuarioAutenticado:
        nivel_usuario = NIVEL_PAPEL.get(usuario_atual.role, 0)
        if nivel_usuario < nivel_exigido:
            log_client.registrar_evento(
                usuario_atual.id,
                f"acesso_negado:{papel_minimo}",
                ip=request.client.host if request.client else None,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Ação exige papel '{papel_minimo}' ou superior",
            )
        return usuario_atual

    return dependencia
