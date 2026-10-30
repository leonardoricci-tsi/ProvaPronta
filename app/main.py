from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from prometheus_client import start_http_server
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import get_settings
from app.routers import (
    admin,
    auth,
    health,
    premium,
    profiles,
    storage_proxy,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # /metrics numa porta interna SEPARADA (9100), sem publicação pro host:
    # quem lê é o Prometheus, de dentro da rede do Docker. O catálogo é o
    # único serviço público — /metrics na porta dele ficaria aberto na
    # internet (rotas, volume de tráfego, taxa de erro).
    # Porta 0 desliga (os testes usam isso — senão cada TestClient tentaria
    # abrir a 9100 de novo).
    porta = get_settings().metrics_port
    if porta:
        start_http_server(porta)
    yield


app = FastAPI(title="ProvaPronta", lifespan=lifespan)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(profiles.router)
app.include_router(premium.router)
# Antes do mount de "/": senão o StaticFiles engole o caminho da foto.
app.include_router(storage_proxy.router)

app.mount("/", StaticFiles(directory="app/static", html=True), name="static")

# Contagem de requisições por rota (o template, ex. /profiles/{usuario_id},
# não o id de verdade) e código de status exato (200, 403, 404... em vez de
# "2xx"), e histograma de latência. O /health fica de fora: o HEALTHCHECK do
# Docker chama a cada 15s e poluiria a contagem com tráfego que não é de usuário.
Instrumentator(
    should_group_status_codes=False,
    excluded_handlers=["/health", "/health/live"],
).instrument(
    app,
    # Faixas do histograma de latência por rota. As padrão (0.1s, 0.5s, 1s)
    # são grossas demais pra calcular p95 útil — só o round-trip até o MySQL
    # remoto já fica entre 0.3 e 0.7s.
    latency_lowr_buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 0.75, 1, 2.5, 5),
)
