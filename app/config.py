from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    # Nome do serviço no docker-compose (rede interna) — o catálogo nunca
    # fala com o auth-service pelo host nem por IP, só por esse DNS interno.
    auth_service_url: str = "http://auth-service:8001"
    # Idem para o log-service (atividade 5) — auditoria dos eventos de
    # negócio e das tentativas negadas (403).
    log_service_url: str = "http://log-service:8002"
    # Object storage (atividade 6): Garage, falado via API S3. Dois endereços
    # porque a URL pré-assinada embute o host na assinatura — o catálogo
    # grava/apaga pela rede interna (s3_endpoint_url), mas assina com o
    # endereço que o navegador abre (s3_public_url): o do PRÓPRIO catálogo,
    # que repassa a foto pro Garage sem porta pública (routers/storage_proxy.py).
    s3_endpoint_url: str = "http://garage:3900"
    s3_public_url: str = "http://localhost:8000"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "api-filmes-perfis"
    # Tem que bater com o `s3_region` do garage.toml, senão a assinatura falha.
    s3_region: str = "garage"
    s3_url_expira_segundos: int = 900
    # Planos pagos (atividade 7), Stripe em MODO DE TESTE. Cada plano é um
    # papel do RBAC: Cinéfilo é o gratuito (todo cadastro nasce nele), Nerd
    # e Stalker do Tom Hanks são vendidos — um `price_...` pra cada.
    # Vazios = venda desligada (checkout responde 503), pra o CI e quem não
    # configurou o Stripe continuarem subindo a stack normalmente.
    stripe_secret_key: str = ""
    stripe_price_nerd: str = ""
    stripe_price_stalker: str = ""
    stripe_webhook_secret: str = ""
    # Pra onde o Stripe manda o navegador de volta depois do checkout.
    catalog_public_url: str = "http://localhost:8000"
    # Porta interna do /metrics (Prometheus). 0 desliga — usado nos testes.
    metrics_port: int = 9100


@lru_cache
def get_settings() -> Settings:
    return Settings()
