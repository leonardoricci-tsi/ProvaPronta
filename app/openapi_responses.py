"""Blocos de resposta reutilizáveis pro Swagger.

Sem `responses=` explícito, o FastAPI só documenta o caminho de sucesso (e
o 422 automático de validação de body/query) — todo `HTTPException` que o
código levanta (401, 403, 404, 409, 502...) aparece como "Undocumented" no
Swagger UI até alguém clicar em "Try it out" e ver na marra. Esses helpers
existem só pra isso: descrever, com exemplo de payload, os erros que cada
rota já levanta de verdade — não duplicam lógica, só documentam o que já
existe (atividade "Documentando suas APIs com Swagger/OpenAPI").
"""


def _erro(descricao: str, detail: str) -> dict:
    return {"description": descricao, "content": {"application/json": {"example": {"detail": detail}}}}


RESP_401 = {401: _erro("Token ausente, inválido ou expirado", "Credenciais inválidas ou expiradas")}

RESP_403_ADMIN = {403: _erro("Autenticado, mas sem papel admin", "Acesso restrito a admins")}


def resp_403_papel(papel_minimo: str) -> dict:
    """`papel_minimo` é o menor papel que a rota aceita (ex.:
    "professor_pro") — mesmo texto que `require_papel_minimo` devolve
    de verdade, não uma paráfrase."""
    return {
        403: _erro(
            f"Autenticado, mas com papel abaixo de '{papel_minimo}'",
            f"Ação exige papel '{papel_minimo}' ou superior",
        )
    }


RESP_404 = {404: _erro("Recurso não existe, ou não pertence ao usuário logado", "Recurso não encontrado")}

RESP_403_PERFIL_ALHEIO = {
    403: _erro("Autenticado, mas tentando editar o perfil de outro usuário", "Você só pode editar o próprio perfil")
}

RESP_404_USUARIO = {404: _erro("usuario_id não existe no auth-service", "Usuário não encontrado")}

RESP_ERROS_FOTO = {
    413: _erro("Arquivo acima do tamanho máximo (2 MB)", "Imagem acima de 2 MB"),
    415: _erro(
        "Arquivo não é uma imagem JPEG, PNG ou WEBP válida (conferido pelo conteúdo, não pela extensão)",
        "Envie uma imagem JPEG, PNG ou WEBP",
    ),
}

RESP_502_STORAGE = {
    502: _erro(
        "Object storage (Garage) fora do ar ou recusou a gravação",
        "Armazenamento de arquivos indisponível no momento",
    )
}

RESP_502_AUTH_SERVICE = {
    502: _erro(
        "auth-service fora do ar ou inalcançável pela rede interna",
        "Serviço de autenticação indisponível no momento",
    )
}

RESP_502_LOG_SERVICE = {
    502: _erro(
        "log-service fora do ar ou inalcançável pela rede interna",
        "Serviço de log indisponível no momento",
    )
}

RESP_409_PLANO = {
    409: _erro(
        "O papel atual do usuário já é o do plano pedido ou um acima (ou é admin)",
        "Você já tem esse plano ou um superior",
    )
}

RESP_ERROS_PAGAMENTO = {
    502: _erro(
        "Stripe fora do ar ou recusou a criação do checkout",
        "Provedor de pagamento indisponível no momento",
    ),
    503: _erro(
        "Chaves/preços do Stripe não configurados neste ambiente (venda desligada)",
        "Venda de planos indisponível neste ambiente",
    ),
}

RESP_ERROS_WEBHOOK = {
    400: _erro(
        "Cabeçalho Stripe-Signature ausente, inválido ou velho demais — a chamada não veio do Stripe",
        "Assinatura do webhook inválida",
    ),
    503: _erro(
        "STRIPE_WEBHOOK_SECRET não configurado neste ambiente",
        "Webhook do Stripe não configurado neste ambiente",
    ),
}

RESP_403_LIMITE_FREE = {
    403: _erro(
        "Plano Free no limite (1 turma, 2 provas por mês) — o Pro libera",
        "O plano Free permite 1 turma. Assine o Pro para criar mais.",
    )
}

RESP_409_TURMA_COM_PROVA = {
    409: _erro(
        "A turma ainda tem provas — apague ou mude as provas de turma antes",
        "A turma tem provas: apague as provas antes de apagar a turma",
    )
}

RESP_409_ALUNO_NUMERO = {
    409: _erro("Já existe aluno com esse número de chamada na turma", "Número de chamada já usado nesta turma")
}
