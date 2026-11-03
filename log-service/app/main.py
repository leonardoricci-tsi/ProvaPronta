from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_client import start_http_server
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import get_settings
from app.routers import health, logs


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # /metrics numa porta interna SEPARADA (9100), sem publicação pro host:
    # quem lê é o Prometheus, de dentro da rede do Docker. Mesmo esquema do
    # catálogo, por consistência (o Prometheus lê todo mundo em <serviço>:9100).
    # Porta 0 desliga (os testes usam isso — senão cada TestClient tentaria
    # abrir a 9100 de novo).
    porta = get_settings().metrics_port
    if porta:
        start_http_server(porta)
    yield


app = FastAPI(
    title="ProvaPronta — Log Service",
    description="Eventos de auditoria do negócio (Redis Stream `audit_log`).",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(logs.router)

# Contagem de requisições por rota (POST /logs, GET /logs) e código de
# status exato (201, 403... em vez de "2xx"), e histograma de latência.
# O /health fica de fora: o HEALTHCHECK do Docker chama a cada 15s e
# poluiria a contagem com tráfego que não é de usuário.
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
