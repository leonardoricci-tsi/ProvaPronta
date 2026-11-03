"""Leitura e validação de PDF enviado pelo professor — mesma regra pro PDF
anexado à prova e pros PDFs da biblioteca de materiais."""

from fastapi import HTTPException, UploadFile, status

# Livro, apostila, slides: até 10 MB por arquivo.
TAMANHO_MAXIMO = 10 * 1024 * 1024


def ler_pdf_enviado(arquivo: UploadFile) -> bytes:
    # Lê no máximo 1 byte além do limite: o bastante pra saber que passou.
    conteudo = arquivo.file.read(TAMANHO_MAXIMO + 1)
    if len(conteudo) > TAMANHO_MAXIMO:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="PDF acima de 10 MB"
        )
    # Tipo conferido pela assinatura do arquivo, não pela extensão nem pelo
    # Content-Type que o navegador manda (os dois o cliente escolhe).
    if not conteudo.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Envie um arquivo PDF"
        )
    return conteudo
