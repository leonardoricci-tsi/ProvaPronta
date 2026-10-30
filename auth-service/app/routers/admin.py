from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import require_admin
from app.database import get_db
from app.models import Usuario
from app.models.usuario import PAPEIS_VALIDOS
from app.openapi_responses import RESP_401, RESP_403_ADMIN
from app.schemas.auth import RoleUpdateIn, UsuarioOut

router = APIRouter(prefix="/auth/admin", tags=["admin"])

_RESP_ADMIN = RESP_401 | RESP_403_ADMIN
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
        "description": "usuario_id não existe",
        "content": {"application/json": {"example": {"detail": "Usuário não encontrado"}}},
    },
}


@router.get("/users", response_model=list[UsuarioOut], responses=_RESP_ADMIN)
def listar_usuarios(
    _admin: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[UsuarioOut]:
    """Só admin: lista todos os usuários cadastrados — é o que permite a
    ação exclusiva de admin desta atividade (promover/rebaixar o papel de
    alguém, olhando essa lista pra decidir quem)."""
    return db.query(Usuario).order_by(Usuario.id).all()


@router.patch(
    "/users/{usuario_id}/role",
    response_model=UsuarioOut,
    responses=_RESP_ADMIN | _RESP_PAPEL_INVALIDO_OU_USUARIO_NAO_ENCONTRADO,
)
def alterar_papel_usuario(
    usuario_id: int,
    dados: RoleUpdateIn,
    _admin: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UsuarioOut:
    """Só admin: promove ou rebaixa o papel de qualquer usuário. Essa é a
    ação exclusiva de admin de verdade — recusa com 403 quem não for
    admin, mesmo chamando o endpoint direto (dependência require_admin)."""
    if dados.role not in PAPEIS_VALIDOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Papel inválido. Use um de: {', '.join(PAPEIS_VALIDOS)}",
        )

    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

    usuario.role = dados.role
    db.commit()
    db.refresh(usuario)
    return usuario
