from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.auth.dependencies import UsuarioAutenticado, require_admin
from app.openapi_responses import RESP_401, RESP_403_ADMIN, RESP_502_LOG_SERVICE
from app.services import log_client

router = APIRouter(prefix="/admin", tags=["admin"])

_RESP_ADMIN = RESP_401 | RESP_403_ADMIN


@router.get("/logs", responses=_RESP_ADMIN | RESP_502_LOG_SERVICE)
def consultar_logs(
    limit: int = Query(50, ge=1, le=1000),
    authorization: str | None = Header(None),
    _usuario_atual: UsuarioAutenticado = Depends(require_admin),
) -> JSONResponse:
    """Só admin: consulta os últimos N eventos de auditoria (atividade 5).

    Log-service não tem porta publicada pro host (mesmo princípio do
    auth-service), então essa rota é a única forma de um admin consultar o
    log de fora — o catálogo já barra com 403 quem não for admin
    (`require_admin`, mesmo enforcement da atividade 4) e repassa o header
    Authorization original pro log-service, que confere de novo com o
    mesmo JWT: defesa em profundidade, não round-trip redundante à toa."""
    try:
        resposta = log_client.consultar_eventos(limit, authorization)
    except log_client.LogServiceUnavailable as erro:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(erro)) from erro
    return JSONResponse(status_code=resposta.status_code, content=resposta.json())
