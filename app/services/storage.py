import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.config import get_settings

_client_interno = None
_client_publico = None


class StorageUnavailable(Exception):
    """O object storage (Garage) não respondeu ou recusou a operação."""


def _criar_client(endpoint_url: str):
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(
            signature_version="s3v4",
            # Path-style (host/bucket/chave): o Garage não tem DNS de
            # subdomínio por bucket configurado aqui.
            s3={"addressing_style": "path"},
            connect_timeout=5,
            read_timeout=10,
            retries={"max_attempts": 2},
        ),
    )


def _get_client_interno():
    """Client pra gravar/apagar — fala com o Garage pela rede interna do
    Docker (http://garage:3900)."""
    global _client_interno
    if _client_interno is None:
        _client_interno = _criar_client(get_settings().s3_endpoint_url)
    return _client_interno


def _get_client_publico():
    """Client só pra assinar URL — nunca faz chamada de rede. A assinatura
    SigV4 inclui o host, então precisa ser gerada com o endereço que o
    navegador vai abrir, não com o `garage:3900` que só existe dentro da
    rede do Docker."""
    global _client_publico
    if _client_publico is None:
        _client_publico = _criar_client(get_settings().s3_public_url)
    return _client_publico


def enviar_objeto(chave: str, conteudo: bytes, content_type: str) -> None:
    try:
        _get_client_interno().put_object(
            Bucket=get_settings().s3_bucket,
            Key=chave,
            Body=conteudo,
            ContentType=content_type,
        )
    except (BotoCoreError, ClientError) as erro:
        raise StorageUnavailable("Armazenamento de arquivos indisponível no momento") from erro


def baixar_objeto(chave: str) -> bytes:
    """Lê o objeto inteiro pela rede interna (ex.: o PDF da apostila, pra
    extrair o texto e gerar questões)."""
    try:
        resposta = _get_client_interno().get_object(Bucket=get_settings().s3_bucket, Key=chave)
        return resposta["Body"].read()
    except (BotoCoreError, ClientError) as erro:
        raise StorageUnavailable("Armazenamento de arquivos indisponível no momento") from erro


def apagar_objeto(chave: str) -> None:
    """Best-effort: usado pra limpar a foto antiga depois de uma troca, ou a
    recém-enviada quando o commit no banco falha. Um objeto órfão no bucket
    é lixo, não erro pro usuário — por isso a falha é engolida."""
    try:
        _get_client_interno().delete_object(Bucket=get_settings().s3_bucket, Key=chave)
    except (BotoCoreError, ClientError):
        pass


def verificar_bucket() -> None:
    """Pro /health: o Garage responde e o bucket existe (HEAD, sem baixar nada)."""
    try:
        _get_client_interno().head_bucket(Bucket=get_settings().s3_bucket)
    except (BotoCoreError, ClientError) as erro:
        raise StorageUnavailable("Armazenamento de arquivos indisponível no momento") from erro


def gerar_url_temporaria(chave: str) -> str:
    """URL pré-assinada (GET) que expira em `s3_url_expira_segundos`. O
    bucket continua privado: sem essa assinatura, o Garage não serve nada."""
    settings = get_settings()
    return _get_client_publico().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": chave},
        ExpiresIn=settings.s3_url_expira_segundos,
    )
