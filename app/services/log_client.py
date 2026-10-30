import httpx

from app.config import get_settings

_http_client: httpx.Client | None = None


class LogServiceUnavailable(Exception):
    """O log-service não respondeu (fora do ar, rede interna com problema)."""


def _get_http_client() -> httpx.Client:
    global _http_client
    if _http_client is None:
        settings = get_settings()
        _http_client = httpx.Client(base_url=settings.log_service_url, timeout=5.0)
    return _http_client


def registrar_evento(usuario_id: int, acao: str, ip: str | None = None) -> None:
    """Dispara o evento de auditoria pro log-service (atividade 5).

    Fire-and-forget: uma falha aqui (log-service fora do ar, rede interna
    com problema) nunca pode derrubar a ação real do usuário — criar uma prova
    ou logar não podem virar 500 por causa de um serviço que só
    observa. Timeout curto e erro engolido de propósito."""
    try:
        _get_http_client().post(
            "/logs", json={"usuario_id": usuario_id, "acao": acao, "ip": ip}
        )
    except Exception:  # noqa: BLE001 — auditoria nunca pode derrubar a ação real
        pass


def consultar_eventos(limit: int, authorization: str | None) -> httpx.Response:
    """Repassa `GET /admin/logs` pro log-service — mesmo princípio do proxy
    de `/auth/admin/users` pro auth-service: o catálogo encaminha o header
    Authorization original, e quem decide se o chamador pode ver (role
    admin, mesmo JWT_SECRET) é o próprio log-service."""
    headers = {"Authorization": authorization} if authorization else {}
    try:
        return _get_http_client().get("/logs", params={"limit": limit}, headers=headers)
    except httpx.RequestError as erro:
        raise LogServiceUnavailable("Serviço de log indisponível no momento") from erro
