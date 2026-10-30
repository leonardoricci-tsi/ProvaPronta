import itertools
import os

# Ambiente dos testes, definido ANTES de importar o app (o Settings lê as
# variáveis na primeira chamada e fica em cache). Variável de ambiente vence
# o .env, então a suíte nunca depende do .env de quem roda — nem lê segredo
# de verdade — e roda igual no CI, onde não existe .env nenhum:
# - segredos fictícios: tudo que usaria banco/storage é SQLite em
#   memória ou mock, nada aqui autentica em serviço real;
# - serviços internos numa porta local fechada: chamada que um teste não
#   mockou (ex.: o evento de auditoria fire-and-forget de um 403) falha na
#   hora, em vez de sair pra rede — sem isso, resolver o nome
#   "log-service" fora do Docker pode travar a suíte.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["JWT_SECRET"] = "teste-jwt-secret-fake"
os.environ["AUTH_SERVICE_URL"] = "http://127.0.0.1:9"
os.environ["LOG_SERVICE_URL"] = "http://127.0.0.1:9"
os.environ["S3_ENDPOINT_URL"] = "http://127.0.0.1:9"
# Sem servidor de métricas na 9100: cada TestClient reabriria a porta.
os.environ["METRICS_PORT"] = "0"

# Imports a partir daqui de propósito depois do ambiente acima.
import jwt
import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.database import Base, get_db
from app.main import app

_proximo_usuario_id = itertools.count(1)


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def criar_token(
    usuario_id: int | None = None, role: str = "professor_pro", nome: str = "Usuário Teste"
) -> str:
    """Gera um JWT do jeito que o auth-service geraria — o catálogo só
    verifica a assinatura localmente, não tem mais tabela de usuários pra
    consultar, então os testes não precisam de um
    usuário "de verdade": só de um token válido com um usuario_id qualquer.

    Papel padrão é "professor_pro" (não o mínimo "professor"), um papel
    pago comum, sem os poderes de coordenador nem de admin.
    """
    if usuario_id is None:
        usuario_id = next(_proximo_usuario_id)
    settings = get_settings()
    payload = {"sub": str(usuario_id), "role": role, "nome": nome}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def auth_service():
    """Mocka o `GET /auth/users/{id}` do auth-service (de onde vem o nome), o
    `PUT /internal/users/{id}/role` (plano pago) e o log-service, que o
    catálogo chama em fire-and-forget."""
    settings = get_settings()
    auth_url, log_url = settings.auth_service_url, settings.log_service_url
    with respx.mock(assert_all_called=False) as mock:
        mock.get(url__regex=rf"{auth_url}/auth/users/(?P<id>\d+)").mock(
            side_effect=lambda request, id: Response(200, json={"id": int(id), "nome": f"Usuário {id}"})
        )
        mock.post(f"{log_url}/logs").mock(return_value=Response(201, json={"id": "1-0"}))
        # Troca de papel pelo plano pago (atividade 7) — rota interna.
        mock.put(url__regex=rf"{auth_url}/internal/users/(?P<id>\d+)/role", name="definir_papel").mock(
            side_effect=lambda request, id: Response(200, json={"id": int(id)})
        )
        yield mock
