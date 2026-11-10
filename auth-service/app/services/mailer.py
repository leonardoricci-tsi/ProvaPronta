import smtplib
from email.message import EmailMessage
from html import escape

from app.config import get_settings

ASSUNTO_REDEFINICAO = "Redefinir sua senha — ProvaPronta"


def _corpo_texto(link: str) -> str:
    return (
        "Olá!\n\n"
        "Recebemos um pedido para redefinir a senha da sua conta no ProvaPronta.\n\n"
        f"Abra o link abaixo para criar uma senha nova (vale por 30 minutos):\n{link}\n\n"
        "Se não foi você, é só ignorar este e-mail: sua senha continua a mesma.\n\n"
        "— ProvaPronta · provas prontas para professores"
    )


def _corpo_html(link: str) -> str:
    # Cores do design system "Caderno" (frontend/src/styles.css). Tudo
    # inline: cliente de e-mail ignora <style> e folha externa.
    link_seguro = escape(link, quote=True)
    return f"""\
<!doctype html>
<html lang="pt-BR">
<body style="margin:0;padding:24px;background:#F6F7F3;font-family:'Segoe UI',Arial,sans-serif;color:#1A1F2B">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;margin:0 auto">
    <tr><td style="padding:0 0 16px;font-size:20px;font-weight:800">
      <span style="display:inline-block;width:28px;height:28px;border-radius:7px;background:#2747B8;color:#FFFFFF;text-align:center;line-height:28px;font-size:16px;vertical-align:middle">&#10003;</span>
      <span style="vertical-align:middle">Prova<span style="color:#2747B8">Pronta</span></span>
    </td></tr>
    <tr><td style="background:#FFFFFF;border:1px solid #DADDD3;border-radius:16px;padding:32px">
      <h1 style="margin:0 0 12px;font-size:22px">Redefinir sua senha</h1>
      <p style="margin:0 0 24px;line-height:1.55;color:#4F5666">
        Recebemos um pedido para redefinir a senha da sua conta. O link vale por 30 minutos.
      </p>
      <a href="{link_seguro}" style="display:inline-block;background:#2747B8;color:#FFFFFF;text-decoration:none;font-weight:700;padding:12px 22px;border-radius:10px">
        Criar senha nova
      </a>
      <p style="margin:24px 0 0;font-size:14px;line-height:1.55;color:#4F5666">
        Se o botão não abrir, copie este endereço no navegador:<br>
        <a href="{link_seguro}" style="color:#2747B8;word-break:break-all">{link_seguro}</a>
      </p>
      <p style="margin:24px 0 0;font-size:14px;color:#4F5666">
        Se não foi você, é só ignorar este e-mail: sua senha continua a mesma.
      </p>
    </td></tr>
    <tr><td style="padding:16px 0 0;font-size:13px;color:#4F5666">ProvaPronta · provas prontas para professores</td></tr>
  </table>
</body>
</html>
"""


def montar_email_redefinicao(email: str, link: str) -> EmailMessage:
    settings = get_settings()
    mensagem = EmailMessage()
    mensagem["Subject"] = ASSUNTO_REDEFINICAO
    mensagem["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    mensagem["To"] = email
    # Texto puro primeiro, HTML como alternativa: quem não renderiza HTML
    # (ou bloqueia) ainda recebe o link.
    mensagem.set_content(_corpo_texto(link))
    mensagem.add_alternative(_corpo_html(link), subtype="html")
    return mensagem


ASSUNTO_PAGAMENTO_RECUSADO = "Não conseguimos cobrar sua assinatura — ProvaPronta"

NOMES_PLANOS = {"professor_pro": "Professor Pro", "coordenador": "Escola / Coordenador"}


def montar_email_pagamento_recusado(email: str, nome: str, plano: str | None, link: str) -> EmailMessage:
    """Atividade 11: a cobrança mensal foi recusada (invoice.payment_failed).
    A conta voltou pro Free até o pagamento passar."""
    settings = get_settings()
    nome_plano = NOMES_PLANOS.get(plano or "", "pago")
    texto = (
        f"Olá, {nome}!\n\n"
        f"Não conseguimos cobrar a mensalidade do seu plano {nome_plano} no ProvaPronta.\n"
        "Enquanto o pagamento não for regularizado, sua conta fica no plano Free.\n\n"
        f"Atualize o cartão em \"Gerenciar assinatura\", na página de planos:\n{link}\n\n"
        "Assim que o pagamento passar, o plano volta sozinho.\n\n"
        "— ProvaPronta · provas prontas para professores"
    )
    link_seguro = escape(link, quote=True)
    html = f"""\
<!doctype html>
<html lang="pt-BR">
<body style="margin:0;padding:24px;background:#F6F7F3;font-family:'Segoe UI',Arial,sans-serif;color:#1A1F2B">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;margin:0 auto">
    <tr><td style="padding:0 0 16px;font-size:20px;font-weight:800">Prova<span style="color:#2747B8">Pronta</span></td></tr>
    <tr><td style="background:#FFFFFF;border:1px solid #DADDD3;border-radius:16px;padding:32px">
      <h1 style="margin:0 0 12px;font-size:22px">Não conseguimos cobrar sua assinatura</h1>
      <p style="margin:0 0 12px;line-height:1.55;color:#4F5666">
        Olá, {escape(nome)}! A mensalidade do plano <strong>{escape(nome_plano)}</strong> foi recusada.
        Enquanto o pagamento não for regularizado, sua conta fica no plano Free.
      </p>
      <p style="margin:0 0 24px;line-height:1.55;color:#4F5666">Assim que o pagamento passar, o plano volta sozinho.</p>
      <a href="{link_seguro}" style="display:inline-block;background:#2747B8;color:#FFFFFF;text-decoration:none;font-weight:700;padding:12px 22px;border-radius:10px">
        Atualizar pagamento
      </a>
    </td></tr>
    <tr><td style="padding:16px 0 0;font-size:13px;color:#4F5666">ProvaPronta · provas prontas para professores</td></tr>
  </table>
</body>
</html>
"""
    mensagem = EmailMessage()
    mensagem["Subject"] = ASSUNTO_PAGAMENTO_RECUSADO
    mensagem["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    mensagem["To"] = email
    mensagem.set_content(texto)
    mensagem.add_alternative(html, subtype="html")
    return mensagem


def _enviar(mensagem: EmailMessage) -> None:
    settings = get_settings()
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(mensagem)
    except (smtplib.SMTPException, OSError) as erro:
        print(f"[mailer] falha ao enviar \"{mensagem['Subject']}\" para {mensagem['To']}: {erro}", flush=True)


def send_payment_failed_email(email: str, nome: str, plano: str | None, link: str) -> None:
    _enviar(montar_email_pagamento_recusado(email, nome, plano, link))


def send_reset_email(email: str, link: str) -> None:
    settings = get_settings()
    mensagem = montar_email_redefinicao(email, link)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(mensagem)
    except (smtplib.SMTPException, OSError) as erro:
        print(f"[mailer] falha ao enviar e-mail de redefinição para {email}: {erro}", flush=True)
