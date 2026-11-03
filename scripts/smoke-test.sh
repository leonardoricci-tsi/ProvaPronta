#!/usr/bin/env bash
# Smoke test da stack inteira de pé (atividade extra de CI/CD): não usa mock
# nenhum — fala com o catálogo real, que fala com o auth-service, o MySQL, o
# log-service/Redis e o Garage de verdade. Roda no CI depois do
# `docker compose up`; qualquer passo que falhar sai com código != 0 e deixa
# o pipeline vermelho.
#
# Uso: scripts/smoke-test.sh [URL do catálogo, padrão http://localhost:8000]
# (as chamadas `docker compose exec` herdam COMPOSE_FILE/COMPOSE_PROJECT_NAME
# do ambiente, igual ao resto do workflow)
set -euo pipefail

BASE="${1:-http://localhost:8000}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

passo() { printf '\n▶ %s\n' "$1"; }
ok() { printf '  ✅ %s\n' "$1"; }
falha() { printf '  ❌ %s\n' "$1"; exit 1; }

# status HTTP + corpo em $TMP/corpo; uso: http METODO URL [args extras do curl]
http() {
  local metodo="$1" url="$2"; shift 2
  curl -sS -o "$TMP/corpo" -w '%{http_code}' -X "$metodo" "$url" "$@"
}
esperar() { # esperar STATUS_ESPERADO STATUS_OBTIDO DESCRIÇÃO
  [ "$2" = "$1" ] && ok "$3 → $2" || { cat "$TMP/corpo" 2>/dev/null; echo; falha "$3 → esperado $1, veio $2"; }
}
json() { python3 -c "import sys,json; print(json.load(open('$TMP/corpo'))$1)"; }
sub_do_jwt() {
  python3 -c "import sys,json,base64; p=sys.argv[1].split('.')[1]; p+='='*(-len(p)%4); print(json.loads(base64.urlsafe_b64decode(p))['sub'])" "$1"
}

passo "Catálogo no ar"
for _ in $(seq 1 60); do
  [ "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/openapi.json")" = "200" ] && break
  sleep 2
done
esperar 200 "$(http GET "$BASE/openapi.json")" "GET /openapi.json"

SUFIXO="$(date +%s)$RANDOM"
SENHA="smoke-$(openssl rand -hex 8)"

# Corpo JSON montado com printf numa variável, nunca com \" dentro de
# "$( ... )": o bash 3.2 (o do macOS) quebra essas aspas e expande as
# vírgulas do JSON como {a,b} — o curl recebia o corpo picotado.
corpo_json() { printf "$@"; }

cadastrar() { # cadastrar NOME EMAIL → imprime o token
  local corpo
  corpo="$(corpo_json '{"nome":"%s","email":"%s","senha":"%s"}' "$1" "$2" "$SENHA")"
  esperar 201 "$(http POST "$BASE/auth/register" -H 'Content-Type: application/json' -d "$corpo")" \
    "POST /auth/register ($1)" >&2
  json "['access_token']"
}

passo "Cadastro e login (catálogo → auth-service → MySQL)"
EMAIL_A="smoke-a-$SUFIXO@example.com"
cadastrar "Smoke A" "$EMAIL_A" > /dev/null
LOGIN_CERTO="$(corpo_json '{"email":"%s","senha":"%s"}' "$EMAIL_A" "$SENHA")"
LOGIN_ERRADO="$(corpo_json '{"email":"%s","senha":"senha-errada"}' "$EMAIL_A")"
esperar 200 "$(http POST "$BASE/auth/login" -H 'Content-Type: application/json' -d "$LOGIN_CERTO")" \
  "POST /auth/login com a senha certa"
TOKEN_A="$(json "['access_token']")"
ID_A="$(sub_do_jwt "$TOKEN_A")"
esperar 401 "$(http POST "$BASE/auth/login" -H 'Content-Type: application/json' -d "$LOGIN_ERRADO")" \
  "POST /auth/login com a senha errada"
esperar 200 "$(http GET "$BASE/auth/me" -H "Authorization: Bearer $TOKEN_A")" "GET /auth/me"
[ "$(json "['email']")" = "$EMAIL_A" ] && ok "/auth/me devolve o usuário certo" || falha "/auth/me devolveu outro usuário"

passo "Perfil e upload de foto (catálogo → Garage + MySQL)"
esperar 200 "$(http GET "$BASE/profiles/$ID_A" -H "Authorization: Bearer $TOKEN_A")" "GET /profiles/$ID_A"
# PNG 64x64 gerado só com a biblioteca padrão (o runner não tem Pillow).
python3 - "$TMP/foto.png" <<'PY'
import struct, sys, zlib
w = h = 64
linhas = b"".join(b"\x00" + bytes((217, 164, 65)) * w for _ in range(h))
def bloco(tipo, dados):
    return struct.pack(">I", len(dados)) + tipo + dados + struct.pack(">I", zlib.crc32(tipo + dados))
open(sys.argv[1], "wb").write(
    b"\x89PNG\r\n\x1a\n" + bloco(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    + bloco(b"IDAT", zlib.compress(linhas)) + bloco(b"IEND", b""))
PY
esperar 200 "$(http POST "$BASE/profiles/$ID_A/foto" -H "Authorization: Bearer $TOKEN_A" \
  -F "arquivo=@$TMP/foto.png;type=image/png")" "POST /profiles/$ID_A/foto (PNG de verdade)"
FOTO_URL="$(json "['foto_url']")"
case "$FOTO_URL" in
  *X-Amz-Signature=*) ok "foto_url é pré-assinada" ;;
  *) falha "foto_url sem assinatura: $FOTO_URL" ;;
esac
esperar 200 "$(http GET "$FOTO_URL")" "GET foto_url (Garage via catálogo)"
esperar 403 "$(http GET "${FOTO_URL%%\?*}")" "GET da mesma foto SEM assinatura (bucket privado)"
printf 'isso nao e imagem' > "$TMP/falsa.png"
esperar 415 "$(http POST "$BASE/profiles/$ID_A/foto" -H "Authorization: Bearer $TOKEN_A" \
  -F "arquivo=@$TMP/falsa.png;type=image/png")" "POST de arquivo falso com extensão .png"

passo "Só o dono edita o perfil"
TOKEN_B="$(cadastrar "Smoke B" "smoke-b-$SUFIXO@example.com")"
esperar 403 "$(http PATCH "$BASE/profiles/$ID_A" -H "Authorization: Bearer $TOKEN_B" \
  -H 'Content-Type: application/json' -d '{"bio":"invadido"}')" "B editando o perfil de A"
esperar 403 "$(http POST "$BASE/profiles/$ID_A/foto" -H "Authorization: Bearer $TOKEN_B" \
  -F "arquivo=@$TMP/foto.png;type=image/png")" "B enviando foto pro perfil de A"
esperar 401 "$(http GET "$BASE/profiles/$ID_A")" "GET /profiles sem token"

passo "Turma, prova e PDF do material (catálogo → MySQL + Garage)"
TURMA="$(corpo_json '{"nome":"1º A","disciplina":"Biologia","ano_letivo":2026}')"
esperar 201 "$(http POST "$BASE/turmas" -H "Authorization: Bearer $TOKEN_A" \
  -H 'Content-Type: application/json' -d "$TURMA")" "POST /turmas"
ID_TURMA="$(json "['id']")"
PROVA="$(corpo_json '{"turma_id":%s,"titulo":"P1","questoes":[{"enunciado":"2+2?","alternativas":["3","4"],"resposta_correta":1}]}' "$ID_TURMA")"
esperar 201 "$(http POST "$BASE/provas" -H "Authorization: Bearer $TOKEN_A" \
  -H 'Content-Type: application/json' -d "$PROVA")" "POST /provas"
ID_PROVA="$(json "['id']")"
printf '%%PDF-1.4\n%%%%EOF\n' > "$TMP/material.pdf"
esperar 200 "$(http POST "$BASE/provas/$ID_PROVA/material" -H "Authorization: Bearer $TOKEN_A" \
  -F "arquivo=@$TMP/material.pdf;type=application/pdf")" "POST /provas/$ID_PROVA/material (PDF)"
esperar 200 "$(http GET "$BASE/provas/$ID_PROVA/material" -H "Authorization: Bearer $TOKEN_A")" \
  "GET link do material"
esperar 200 "$(http GET "$(json "['url']")")" "GET do PDF pela URL pré-assinada"
esperar 404 "$(http GET "$BASE/provas/$ID_PROVA" -H "Authorization: Bearer $TOKEN_B")" "B abrindo a prova de A"
esperar 403 "$(http POST "$BASE/provas/$ID_PROVA/versao-b" -H "Authorization: Bearer $TOKEN_A")" \
  "versão B no plano Free (papel professor)"

passo "Auditoria (log-service → Redis)"
EVENTOS="$(docker compose exec -T redis redis-cli --raw XREVRANGE audit_log + - COUNT 50)"
for acao in login upload_foto_perfil "acesso_negado:perfil:$ID_A" "turma_criada:$ID_TURMA" \
  "prova_criada:$ID_PROVA" "material_enviado:prova:$ID_PROVA" "acesso_negado:professor_pro"; do
  grep -qx "$acao" <<< "$EVENTOS" && ok "evento '$acao' gravado" || falha "evento '$acao' não chegou no log"
done

printf '\n🎉 Smoke test OK — stack inteira respondendo de verdade.\n'
