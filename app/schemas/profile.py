from pydantic import BaseModel, Field


class PerfilUpdateIn(BaseModel):
    # Só bio. Não existe campo de usuario_id aqui de propósito: se o cliente
    # mandar um no corpo, o Pydantic ignora — quem é o dono vem do JWT.
    bio: str = Field(max_length=280)


class PerfilOut(BaseModel):
    usuario_id: int
    nome: str
    bio: str
    # URL pré-assinada, temporária (expira em S3_URL_EXPIRA_SEGUNDOS) —
    # gerada a cada leitura, nunca gravada no banco.
    foto_url: str | None
    # Pro front decidir se mostra o botão de editar. É só interface: quem
    # garante a regra é o 403 do PATCH.
    eh_meu: bool
    # Plano pago ativo (atividade 7) — nerd / stalker_do_tomhanks, ou None
    # no gratuito. Vira o selo no perfil, que aparece pra quem visita também.
    plano: str | None
