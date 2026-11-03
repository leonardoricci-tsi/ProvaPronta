from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret: str
    jwt_expire_minutes: int = 60
    jwt_algorithm: str = "HS256"
    # Porta interna do /metrics (Prometheus). 0 desliga — usado nos testes.
    metrics_port: int = 9100
    # Nome do serviço no docker-compose (rede interna) — auditoria de login
    # e de tentativa negada (403) nas rotas de admin (atividade 5).
    log_service_url: str = "http://log-service:8002"
    # URL pública do catálogo — é ele o único ponto de entrada de fora, então
    # o link de redefinição de senha aponta pra lá (não pro auth-service,
    # que não tem porta publicada).
    catalog_public_url: str = "http://localhost:8000"
    # SMTP de dev (Mailtrap) — em produção essas mesmas variáveis apontam pro
    # Resend com domínio próprio (smtp.resend.com:587, usuário "resend",
    # senha = API key, remetente no domínio verificado), sem
    # mudar nenhuma linha de código, só o .env. O mailer usa STARTTLS, então
    # a porta tem que ser a 587 (a 465 é SSL direto e não funciona aqui).
    smtp_host: str = "sandbox.smtp.mailtrap.io"
    smtp_port: int = 587
    smtp_user: str
    smtp_password: str
    smtp_from_email: str = "no-reply@provapronta.local"
    smtp_from_name: str = "ProvaPronta"


@lru_cache
def get_settings() -> Settings:
    return Settings()
