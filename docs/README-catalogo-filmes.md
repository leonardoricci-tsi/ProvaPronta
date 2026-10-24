> **Documento herdado.** Este era o README do catálogo de filmes do Tom Hanks (atividades 1 a 8), movido sem alterações de conteúdo quando o projeto virou o [ProvaPronta](../README.md) (atividade 9). Descreve o código como ele está até a troca começar na atividade 10.

# Catálogo de Filmes — Tom Hanks (multi-tenant)

[![CI/CD](https://github.com/leonardoricci-tsi/api_filme_/actions/workflows/ci.yml/badge.svg)](https://github.com/leonardoricci-tsi/api_filme_/actions/workflows/ci.yml)

> Atividade da disciplina, proposta pelo professor [@siriani](https://github.com/siriani).
>
> **Relatório da P1 (ISW055):** [docs/P1_ISW055_Leonardo_Oliveira_assinado.pdf](P1_ISW055_Leonardo_Oliveira_assinado.pdf) (assinado digitalmente via gov.br) — fonte em Typst: [docs/P1_ISW055_Leonardo_Oliveira.typ](P1_ISW055_Leonardo_Oliveira.typ).

API FastAPI que lista filmes do Tom Hanks (dados sempre ao vivo da TMDB, nunca persistidos) e permite que cada usuário cadastrado no app favorite e comente filmes, com isolamento total de dados entre usuários proposto pelo professor @siriani.

**Atividade 3 — serviços desacoplados:** a autenticação (login, cadastro, papéis de usuário e recuperação de senha) foi extraída do catálogo para um microsserviço próprio, o `auth-service/`, que só é alcançável pela rede interna do Docker. O catálogo continua sendo o único ponto de entrada público. Veja a seção [Arquitetura](#arquitetura) e as [evidências](#evidências) mais abaixo.

**Atividade 6 — armazenamento de objetos:** o catálogo virou uma rede social simples: cada usuário tem uma página de perfil com foto, bio e os filmes favoritados. A foto **não vai pro banco** — vai pra um object storage (Garage, compatível com S3), e o MySQL guarda só a chave do objeto. Veja a seção [Perfil e fotos](#perfil-e-fotos-object-storage-atividade-6).

**Atividade 7 — serviço baseado em pagamento:** o catálogo ganhou um modelo de negócio. Os níveis de fã viraram planos: **Cinéfilo** (gratuito), **Nerd** (R$ 19,90/mês) e **Stalker do Tom Hanks** (R$ 9.999,90/mês), cobrados pelo **Stripe em modo de teste**. O cartão é digitado na página hospedada pelo Stripe e nunca chega no backend; o pagamento é confirmado por **webhook com assinatura validada**, que troca o papel do usuário e libera as funções do plano. Veja a seção [Planos pagos](#planos-pagos-stripe-atividade-7).

**Atividade extra — CI/CD com GitHub Actions:** deploy sem clicar em nada. A cada `git push`, o GitHub Actions roda os testes, builda as imagens e sobe a stack inteira pra um smoke test; se tudo passou, publica as imagens no GHCR com a tag do commit (`sha-xxxxxxx`) e o Portainer coloca essa versão no ar sozinho. Veja a seção [CI/CD](#cicd-github-actions-atividade-extra).

**Atividade extra — Observabilidade:** cada serviço agora diz como está de saúde, sem ninguém abrir um terminal. `/health` com readiness de verdade (testa MySQL, Redis, Garage e devolve `503` quando uma dependência crítica cai), `HEALTHCHECK` do Docker em todos os containers, `/metrics` pro Prometheus e um painel no Grafana (bônus). Veja a seção [Observabilidade](#observabilidade-health-checks-e-métricas-atividade-extra).

**Atividade 8 — SaaS, PaaS, IaaS e documentação reversa:** nenhuma linha de código nova. O sistema foi documentado do zero, como se tivesse sido herdado de outra pessoa: especificação, arquitetura, regras de negócio (extraídas do código, com o arquivo de cada uma) e modelo de dados ficam em **[DOCUMENTACAO.md](../DOCUMENTACAO.md)**. Aqui no README fica a classificação de cada peça do projeto nas camadas de nuvem: seção [Camadas de nuvem](#camadas-de-nuvem-saas-paas-e-iaas-atividade-8).

## Camadas de nuvem: SaaS, PaaS e IaaS (atividade 8)

As três siglas dizem quanto da pilha eu administro e quanto o provedor administra por mim. O projeto usa as três ao mesmo tempo:

```
SaaS   Stripe · Mailtrap/Brevo · TMDB · GitHub · GHCR · Cloudflare      só consumo, não hospedo nada
PaaS   catálogo · auth-service · log-service · Redis · Garage           entrego imagem, o Docker/Portainer roda
       MySQL da disciplina · GitHub Actions
IaaS   VM do servidor da disciplina (Proxmox, Linux + Docker)           máquina, disco e rede
```

| Peça | Camada | Por quê |
|---|---|---|
| VM do servidor da disciplina (Proxmox) | **IaaS** | É a base de tudo: máquina virtual, disco e rede. Sistema operacional, Docker e Portainer são instalados e mantidos por quem administra a VM, não pelo provedor do hardware. |
| Catálogo (`api`) | **PaaS** | Eu entrego só a imagem (`ghcr.io/.../api-filmes:sha-...`); o Docker na VM, gerenciado pelo Portainer, cuida de rodar, reiniciar (`restart: unless-stopped`) e conferir a saúde (`HEALTHCHECK`). Não instalo SO pra subir uma versão nova. |
| `auth-service` | **PaaS** | Mesmo modelo do catálogo: imagem própria, implantada pela stack do Portainer a partir do repositório (GitOps). |
| `log-service` | **PaaS** | Idem: só a imagem é minha; runtime, rede interna e reinício são da plataforma. |
| Redis | **PaaS** (auto-hospedado) | Uso a imagem oficial `redis:7-alpine` como serviço pronto, só configuro. Numa nuvem pública seria um Redis gerenciado (ElastiCache, Memorystore). |
| Garage (no lugar do MinIO) | **PaaS** (auto-hospedado) | Object storage com API S3, rodando como container na mesma plataforma. O código fala S3 puro (`boto3`); trocar por um S3 gerenciado seria só configuração. |
| MySQL remoto | **PaaS** (banco como serviço) | A disciplina provisiona a instância e me entrega uma `DATABASE_URL`. Eu crio as tabelas (Alembic), mas não administro servidor, SO nem backup. |
| GitHub Actions | **PaaS** | Eu entrego o workflow (`.github/workflows/ci.yml`); o GitHub fornece e descarta a máquina que roda testes, build e smoke test. |
| Stripe | **SaaS** | Pagamento pronto: página de checkout, cobrança recorrente e webhook. O cartão nem passa pelo meu backend. Só uso a API e o painel. |
| Mailtrap (dev) / Brevo (prod) | **SaaS** | Provedor de e-mail transacional: o `auth-service` só abre uma conexão SMTP e manda a mensagem do "esqueci minha senha". Entrega e reputação do remetente são deles. |
| API da TMDB | **SaaS** | Todos os dados de filmes (lista, elenco, onde assistir, pôsteres) vêm ao vivo de lá; o sistema não guarda nenhum. |
| GitHub (repositório) e GHCR (registro de imagens) | **SaaS** | Uso o produto pronto pra guardar código e imagens; não hospedo Git nem registry. |
| Cloudflare (domínio `*.lapps.studio`) | **SaaS** | HTTPS e proxy na frente do servidor da disciplina, configurado pela infraestrutura do curso. Eu só recebo o domínio. |

Prometheus e Grafana só rodam no `docker-compose.yml` local (observabilidade), fora da produção; se subissem, seriam PaaS auto-hospedado como o Redis.

A divisão não é rígida: o mesmo container é "PaaS" pra mim porque alguém já cuidou da VM e do Docker. Se eu tivesse que criar a VM, instalar o Linux e o Docker, a camada de baixo seria trabalho meu, e o projeto inteiro desceria um nível. Detalhes de cada serviço e de como eles se conectam: [DOCUMENTACAO.md → Arquitetura](../DOCUMENTACAO.md#2-arquitetura).

## Stack
- **Backend:** FastAPI + SQLAlchemy + Alembic (catálogo e `auth-service`, cada um com sua própria migration history)
- **Banco:** MySQL (driver `pymysql`) — a mesma instância remota, compartilhada entre os dois serviços
- **Auth:** microsserviço próprio (`auth-service/`), cadastro/login com senha em hash `bcrypt`, sessão via JWT (assinatura verificada localmente pelo catálogo), papéis `usuario`/`admin`, recuperação de senha por e-mail com token de expiração de 30 minutos
- **Observabilidade:** `/health` (liveness/readiness) + `HEALTHCHECK` do Docker; métricas com `prometheus-fastapi-instrumentator`, coletadas pelo Prometheus e exibidas no Grafana
- **Object storage:** [Garage](https://garagehq.deuxfleurs.fr) (API S3, cliente `boto3`) — fotos de perfil; o banco guarda só a chave do objeto
- **Pagamentos:** [Stripe](https://stripe.com) em modo de teste (SDK `stripe` 16): Checkout Session hospedada pelo Stripe + webhook assinado (HMAC-SHA256)
- **E-mail:** SMTP — Mailtrap em desenvolvimento (sandbox, não entrega de verdade), Brevo em produção
- **Frontend:** Angular (standalone components), build servido como estático pelo próprio FastAPI em produção

## Arquitetura

Cinco containers, uma rede interna, um único ponto de entrada público:

```
Navegador ──HTTPS──▶ Catálogo (api)                MySQL
                      único container com porta      (usuarios, favoritos,
                      publicada pro host              comentarios, reset_tokens)
                          │         │
                          │         │ POST /logs (login, logout, favoritar,
                          │         │ comentar, apagar, 403 negado)
                          │         ▼
                          │     log-service ──XADD──▶ Redis (Stream audit_log)
                          │     SEM porta publicada    SEM porta publicada
                          │     GET /logs = só admin
                          │         ▲
                          │         │ POST /logs (login, 403 negado)
                          │ PUT/DELETE objeto (foto de perfil) + repasse
                          │ da URL pré-assinada ──────────▶ Garage (API S3)
                          │                                 SEM porta publicada
                          │ rede interna do Docker (catalog-net)
                          ▼         │
                      auth-service ─┘
                      login, cadastro, role,
                      esqueci-senha
                      SEM porta publicada ──SMTP──▶ Mailtrap (dev) / Brevo (prod) ──▶ e-mail do usuário
```

- O `auth-service` não tem `ports:` no `docker-compose.yml` — só `expose: "8001"`, acessível apenas de dentro da rede `catalog-net`, pelo nome do serviço (`http://auth-service:8001`). O `log-service` (atividade 5), o `redis` e o `garage` (atividade 6) seguem o mesmo princípio: `expose: "8002"`, `expose: "6379"` e `expose: "3900"`, nenhum alcançável de fora.
- O catálogo é o único container com porta publicada pro host. Toda rota `/auth/*` (registro, login, perfil, esqueci-senha, redefinir senha) é recebida pelo catálogo e repassada internamente pro `auth-service` (`app/services/auth_client.py`).
- Fora de `/auth/*`, o catálogo **não** chama o `auth-service` a cada request: o JWT é assinado pelo `auth-service` mas verificado localmente pelo catálogo (mesmo `JWT_SECRET` nos dois), o que evita um round-trip de rede em toda chamada autenticada.
- Catálogo e `auth-service` são os únicos que decidem o que auditar — nenhum dos dois escreve log de auditoria no próprio banco (MySQL); os dois mandam um evento HTTP (`POST /logs`) pro `log-service`, que é quem sabe gravar num Redis Stream. Detalhes na seção [Auditoria (logs)](#auditoria-logs-atividade-5).
- O JWT carrega um claim `role`; toda rota sensível decide o que aceitar olhando só pra esse claim — nunca por nada que o cliente mande. Veja a seção [Autorização (RBAC)](#autorização-rbac-atividade-4) logo abaixo pros papéis e permissões de verdade.
- O catálogo não é mais dono da tabela `usuarios` — as FKs de `favoritos`/`comentarios` pra `usuarios` foram removidas; o isolamento entre usuários continua garantido, só que via `usuario_id` extraído do JWT, não mais por FK no banco.

## Autorização (RBAC, atividade 4)

**Atividade 4 — controle de acesso por papel:** o campo `role` existia desde a atividade 3, mas não decidia nada — qualquer papel conseguia fazer qualquer coisa. Agora ele decide de verdade, e quem decide é sempre o servidor, nunca a tela: esconder um botão no Angular não é segurança, é só interface. Toda ação sensível é recusada com `403` no backend pra quem não tem o papel certo, mesmo chamando o endpoint direto pelo Postman/curl.

**Atividade 5 — logs e auditoria:** o sistema fazia coisas, mas não lembrava o que fez. Agora todo login, logout, favoritar, comentar, apagar comentário (moderação) e toda tentativa de ação negada por permissão (o `403` da atividade 4) deixa um rastro — quem fez o quê, e quando. Isso é log de auditoria, diferente de log de aplicação (erro/debug): ajuda a entender comportamento de gente, não bugs. Fica num microsserviço próprio, o `log-service/`, gravando em Redis Streams — nem o catálogo nem o `auth-service` escrevem log de auditoria no próprio banco. Veja a seção [Auditoria (logs)](#auditoria-logs-atividade-5) mais abaixo.

### Papéis e permissões

Quatro papéis, empilhados — cada um inclui a permissão do anterior, `admin` é o topo: consome tudo que `stalker_do_tomhanks` consome **e** ainda modera.

| Papel | Pode fazer |
|---|---|
| `cinefilo` (papel padrão no cadastro) | Ver o catálogo de filmes (`GET /movies`, `GET /movies/{id}/detalhes`) |
| `nerd` | Tudo de `cinefilo` **+** comentar e favoritar filmes (`/comments/*`, `/favorites/*`) |
| `stalker_do_tomhanks` | Tudo de `nerd` **+** jogar o quiz do pôster pixelado (`/quiz/pixelado`, exclusivo desse papel pra cima) |
| `admin` | Tudo de `stalker_do_tomhanks` **+** exclusivo dele: apagar comentário/favorito de **qualquer** usuário (`/admin/comments/*`, `/admin/favorites/*`) e listar/promover/rebaixar o papel de qualquer usuário (`GET /auth/admin/users`, `PATCH /auth/admin/users/{id}/role`) |

A escada de nível fica em `app/auth/dependencies.py` (`NIVEL_PAPEL`, `require_papel_minimo`) — `admin` tem o nível mais alto (4), então qualquer rota que exija `nerd`+ ou `stalker_do_tomhanks`+ já libera admin de graça, sem precisar listar o papel em cada rota. As ações **exclusivas** de admin (moderação, promoção) usam uma segunda dependência, `require_admin`, que exige o papel exato — não é "nível mínimo", é "só esse papel mesmo".

### Ação exclusiva de admin

Duas frentes, ambas só admin:
- **Moderação:** `DELETE /admin/comments/{id}` e `DELETE /admin/favorites/{id}` apagam o comentário/favorito de qualquer usuário (não só o próprio); `GET /admin/comments` e `GET /admin/favorites` listam de todo mundo. Tudo dentro do catálogo, checado localmente (`app/routers/admin.py`, `require_admin`).
- **Gestão de usuário:** `GET /auth/admin/users` + `PATCH /auth/admin/users/{id}/role` lista usuários e muda o papel de qualquer um. Como a tabela `usuarios` pertence ao `auth-service` (não ao catálogo, desde a atividade 3), a checagem de `role == "admin"` acontece lá (`auth-service/app/auth/dependencies.py::require_admin`) — o catálogo só repassa a chamada (`app/routers/auth.py`), do mesmo jeito que já repassa `/auth/register` e `/auth/login`.

### Quiz do pôster pixelado (exclusivo de `stalker_do_tomhanks`)

`GET /quiz/pixelado` sorteia um filme do Tom Hanks, baixa o pôster de verdade da TMDB (ao vivo, nunca persistido) e devolve ele pixelado + 4 opções de título. `POST /quiz/pixelado/resposta` confere o palpite — **sempre no servidor**: o cliente nunca recebe a resposta certa antes de enviar a tentativa, só um `round_id` assinado (JWT com o `id` do filme, mesmo `JWT_SECRET` do login) que ele não consegue forjar nem decodificar sem a chave. É o mesmo princípio do RBAC aplicado a outra coisa: nunca confiar em nada que o cliente diga sobre si mesmo.

### Padrão A (centralizado) ou Padrão B (claims no JWT)?

**Padrão B.** O catálogo nunca faz uma chamada de rede pro `auth-service` pra decidir uma permissão em `/comments`, `/favorites` ou `/quiz/*` — o `role` já vem dentro do JWT, assinado, e `require_papel_minimo`/`require_admin` só leem o claim localmente (`app/auth/dependencies.py`). É a exceção de propósito: `/admin/users*` (listar/promover usuário) *é* uma chamada de rede ao `auth-service`, mas não pra checar permissão — é porque a tabela `usuarios` mora lá, não no catálogo; a checagem de `role == "admin"` em si acontece toda dentro do `auth-service`, sem round-trip nenhum.

**Se fosse pro Padrão A:** cada rota de `/comments`, `/favorites` e `/quiz/*` deixaria de ler `usuario_atual.role` do dataclass `UsuarioAutenticado` (que hoje só decodifica o JWT) e passaria a chamar um endpoint novo tipo `POST /auth/pode?acao=comentar` no `auth-service` a cada requisição, esperar a resposta, e só então seguir. Ganharia revogação imediata (rebaixar um `stalker_do_tomhanks` pra `cinefilo` valeria na próxima requisição dele, não só quando o token expirar); perderia velocidade (round-trip de rede extra em toda ação, não só nas de admin) e adicionaria uma dependência de disponibilidade — se o `auth-service` cair, `/comments` e `/favorites` param de funcionar até pra quem já tinha token válido, porque não teria mais como confirmar o papel.

## Auditoria (logs, atividade 5)

Log de auditoria é diferente de log de aplicação (erro, debug, stack trace) — aquele ajuda a entender bugs, este ajuda a entender comportamento de gente: quem fez o quê, e quando. Se um comentário sumir ou um usuário virar admin do nada, é aqui que dá pra responder "o que aconteceu".

### Por que um microsserviço próprio, e por que Redis
Catálogo e `auth-service` já têm banco relacional (MySQL) — poderiam escrever log ali. Mas log de auditoria tem um padrão de uso bem diferente de dado de negócio: escreve muito, lê pouco, quase nunca precisa de transação, e não pode ficar misturado com a tabela que ele audita (se um bug no código do catálogo apagar registros à toa, o rastro do que aconteceu não pode estar no mesmo lugar). Por isso vira um serviço à parte, o `log-service/`, e por isso o MySQL não é a ferramenta certa: **Redis Streams** (`XADD` pra gravar, `XREVRANGE` pra consultar) é pensado exatamente pra log de eventos ordenado no tempo, rápido pra escrita em alto volume — foi a opção escolhida (não a lista simples com `LPUSH`, que perderia a ordenação/timestamp nativos que o Streams já resolve de graça).

### Como o evento chega no log-service
Catálogo e `auth-service` nunca escrevem direto no Redis — mantém a centralização: cada um manda um `POST /logs` pro `log-service` (`app/services/log_client.py` e `auth-service/app/services/log_client.py`), que é quem grava no Stream. A chamada é **fire-and-forget**: se o `log-service` cair, a ação real do usuário (favoritar, comentar, logar) não pode virar erro por causa de um serviço que só observa — a falha é engolida, com timeout curto.

### Eventos auditados
| Evento | `acao` gravada | Onde é decidido |
|---|---|---|
| Login | `login` | `auth-service`, após senha validada |
| Logout | `logout` | Catálogo, `POST /auth/logout` (JWT é stateless — não existe sessão pra invalidar; essa rota só existe pra deixar o rastro) |
| Favoritar filme | `favoritar_filme:{tmdb_movie_id}` | Catálogo, `POST /favorites` |
| Comentar | `comentar:{tmdb_movie_id}` | Catálogo, `POST /comments` |
| Apagar comentário (moderação) | `apagar_comentario_moderacao:{comentario_id}` | Catálogo, `DELETE /admin/comments/{id}` |
| Tentativa negada por permissão (403) | `acesso_negado:{papel}` (ex.: `acesso_negado:admin`, `acesso_negado:nerd`) | Dentro de `require_admin`/`require_papel_minimo`, nos dois serviços — cobre **toda** rota protegida de uma vez, sem precisar logar em cada endpoint separadamente |
| Editar bio (atividade 6) | `atualizar_perfil` | Catálogo, `PATCH /profiles/{id}` |
| Enviar foto de perfil (atividade 6) | `upload_foto_perfil` | Catálogo, `POST /profiles/{id}/foto` |
| Tentar editar o perfil de outro (atividade 6) | `acesso_negado:perfil:{id}` | Dentro de `require_dono_do_perfil`, no catálogo |

Estrutura mínima de cada evento: `usuario_id`, `acao`, `timestamp` (gerado pelo `log-service`, não pelo chamador) e, como bônus, `ip` (`request.client.host` de quem chamou).

### Consultar o log — só admin
`GET /logs` no `log-service` exige `role == "admin"` (decodifica o mesmo JWT localmente, sem round-trip — mesmo princípio do resto do RBAC). Como o `log-service` não tem porta publicada pro host, quem quiser consultar de fora usa `GET /admin/logs` no catálogo: barra com `403` quem não for admin **antes** de sequer tentar o proxy (`app/routers/admin.py`), e repassa o header `Authorization` original pro `log-service`, que confere de novo — defesa em profundidade, não round-trip redundante à toa.

## Perfil e fotos (object storage, atividade 6)

Cada usuário tem uma página de perfil (`/app/perfil/{id}` no front, `GET /profiles/{id}` na API): nome, foto, uma bio curta (até 280 caracteres) e a lista de filmes favoritados. Qualquer usuário logado vê o perfil de qualquer outro — é rede social —, mas **só o dono edita**.

### Por que a foto não mora no banco
Dá pra guardar arquivo numa coluna `BLOB` do MySQL, mas banco relacional é otimizado pra linhas pequenas e consultas estruturadas: cada foto de alguns MB incharia o banco, deixaria backup mais pesado e não escala. Então o upload faz **duas gravações separadas**:

```
Usuário ──foto──▶ Catálogo ──arquivo──▶ Garage   (bucket api-filmes-perfis, chave perfis/{id}/{uuid}.jpg)
                     └──────chave─────▶ MySQL    (tabela perfis, coluna foto_key)
```

Exibir o perfil depois é ler a chave em `perfis.foto_key` e montar a URL na hora — o arquivo binário nunca passa pelo banco.

Ordem das gravações (`POST /profiles/{id}/foto`, `app/routers/profiles.py`): primeiro o arquivo vai pro Garage; se o Garage estiver fora, a resposta é `502` e nada é gravado no banco. Depois a chave vai pro MySQL; se o commit falhar, o objeto recém-enviado é apagado (sem a chave no banco, ninguém acharia esse arquivo de novo). Só depois do commit a foto antiga é apagada do bucket.

### Validação do upload
Em `app/services/imagem.py`, antes de aceitar:
- **Tamanho:** até 2 MB. O servidor lê no máximo 2 MB + 1 byte, então nem carrega na memória um arquivo maior. Acima disso, responde `413`.
- **Tipo:** decidido **pelos bytes do arquivo** (Pillow), nunca pelo `Content-Type` nem pela extensão, que são o cliente dizendo o que quiser. Só JPEG, PNG e WEBP; qualquer outra coisa recebe `415`. Um `shell.php` renomeado pra `foto.png` é recusado.
- **Dimensão:** até 25 milhões de pixels, conferido antes de decodificar (protege contra "decompression bomb", um PNG minúsculo que declara 20000×20000).
- **Reencodagem:** a imagem é reduzida pra no máximo 1024 px e salva de novo. Isso descarta os metadados EXIF, inclusive a **localização GPS** de quem tirou a foto, e qualquer coisa escondida depois do fim da imagem.
- A chave do objeto é gerada pelo servidor (`perfis/{id}/{uuid}.{ext}`); o nome do arquivo que o usuário mandou nunca é usado.

### Exibir a imagem: URL pré-assinada, não bucket público
**Decisão: URL pré-assinada**, válida por 15 minutos (`S3_URL_EXPIRA_SEGUNDOS`), gerada a cada `GET /profiles/{id}`.

| | Bucket com leitura pública | URL pré-assinada (escolhida) |
|---|---|---|
| Configuração | Simples: a URL é fixa e previsível (`/bucket/chave`) | O backend assina uma URL nova a cada leitura (`boto3.generate_presigned_url`, sem chamada de rede) |
| Quem vê a foto | Qualquer um que descobrir ou adivinhar a URL, pra sempre | Só quem recebeu uma URL assinada, e só até ela expirar |
| Link vazado | Continua funcionando indefinidamente | Para de funcionar sozinho em 15 min |
| Cache do navegador | Ótimo (URL estável) | Pior (a URL muda a cada carregamento) |
| No Garage | Nem existe do jeito simples: o Garage **não tem bucket policy/ACL**. Leitura pública só pelo endpoint de *website*, que é outro servidor, outra porta, roteado por nome de host | Suportado direto na API S3 (assinatura SigV4) |

O preço é o cache (a foto é baixada de novo a cada visita ao perfil) e um pouco mais de lógica no backend. Em troca, o bucket nunca fica aberto: sem assinatura, ou com a assinatura adulterada, o Garage responde `403`; com a URL expirada, responde `400` (`Date is too old`). No Garage, a opção "pública" ainda exigiria configurar um endpoint de website à parte, então a pré-assinada ficou mais simples **e** mais segura.

**Detalhe de deploy: uma porta só.** O servidor da disciplina expõe só um domínio HTTPS, o do catálogo. E a página HTTPS não pode carregar imagem de um endereço HTTP (o navegador bloqueia), então o Garage não tem como ter porta pública própria. A solução mantém a URL pré-assinada de verdade:
1. O catálogo assina a URL com o **domínio do próprio catálogo** (`S3_PUBLIC_URL`), por exemplo `https://.../api-filmes-perfis/perfis/7/ab12.jpg?X-Amz-Signature=...`.
2. O navegador pede esse caminho ao catálogo, que repassa pro Garage pela rede interna **sem tocar em nada que entrou na assinatura**: mesmo caminho, mesma query byte a byte, e o mesmo `Host` que foi assinado (`app/routers/storage_proxy.py`).
3. **Quem valida a assinatura e a expiração continua sendo o Garage**; o catálogo não decide nada, só devolve a resposta (`200` com a imagem, `403` sem assinatura válida, `400` se já expirou).

Assim o Garage fica igual ao `auth-service`, ao `log-service` e ao `redis`: sem porta publicada.

### Cada um só edita o próprio perfil
`PATCH /profiles/{id}` (bio) e `POST /profiles/{id}/foto` passam pela dependência `require_dono_do_perfil`, que compara o `{id}` da URL com o `sub` do **JWT**, nunca com algo do corpo da requisição. O schema de entrada nem tem campo `usuario_id`: se alguém mandar um no corpo, o campo é ignorado. Mandar o ID de outra pessoa na URL devolve `403 {"detail":"Você só pode editar o próprio perfil"}` e registra `acesso_negado:perfil:{id}` no log de auditoria (atividade 5). **Nem admin passa**: moderar comentário é uma coisa, reescrever a bio de alguém é outra.

O botão de editar só aparece no próprio perfil (`eh_meu` na resposta), mas isso é interface. Quem garante a regra é o `403`, mesmo chamando a API direto por `curl`.

### De onde vem o nome
O catálogo é dono do perfil (tabela `perfis`: `usuario_id`, `bio`, `foto_key`), mas o nome mora na tabela `usuarios`, do `auth-service`. `GET /profiles/{id}` busca o nome num endpoint interno novo, `GET /auth/users/{id}`, que devolve só `id` e `nome` (sem e-mail nem papel). Igual a `favoritos` e `comentarios`, `perfis` não tem FK pra `usuarios`: outro serviço, outro dono.

### Por que Garage e não MinIO
O enunciado sugere MinIO, mas a edição community dele foi arquivada e perdeu recursos (console, imagens Docker publicadas). O professor liberou a troca. O Garage fala a mesma API S3, então o código do catálogo é o de qualquer S3 (`boto3`), e trocar de volta seria só configuração. A partir da v2.3, `garage server --single-node --default-bucket` monta o cluster de um nó e cria a chave de acesso e o bucket a partir de variáveis de ambiente, sem passo manual de `garage layout`/`garage key`. O `garage/garage.toml` não tem segredo nenhum (o `rpc_secret` vem de `GARAGE_RPC_SECRET`) e vai dentro de uma imagem própria (`garage/Dockerfile`), porque no Portainer não há repositório pra montar o arquivo como volume.

## Planos pagos (Stripe, atividade 7)

Os papéis da [atividade 4](#autorização-rbac-atividade-4) viraram planos, os mesmos três cards da landing page:

| Plano | Papel | Preço | O que libera |
|---|---|---|---|
| 🍿 Cinéfilo | `cinefilo` | **grátis** (todo cadastro nasce nele) | catálogo, sinopse e ficha técnica, perfil |
| 🤓 Nerd | `nerd` | R$ 19,90/mês | + favoritar, comentar |
| 🕵️ Stalker do Tom Hanks | `stalker_do_tomhanks` | R$ 9.999,90/mês | + quiz do pôster pixelado ("fã-clube") |

O benefício de pagar é **o próprio RBAC**: a mesma ação devolve `403` antes e `201` depois do pagamento, do mesmo jeito que a atividade 4 mostrou com papéis. Nada novo pra conferir em cada rota: `require_papel_minimo("nerd")` já fazia isso. A única novidade é como o papel muda: antes só um admin trocava; agora o pagamento troca.

### Por que pagamento é delegado
Guardar dado de cartão exige conformidade PCI-DSS, que este sistema não tem nem deveria tentar ter. Então ele **nunca vê o cartão**: o checkout é uma página **hospedada pelo Stripe** (`checkout.stripe.com`). O banco guarda, no máximo, os IDs que o Stripe devolve:

```
assinaturas (catálogo)
  usuario_id              PK (sem FK, igual perfis/favoritos: usuarios é de outro serviço)
  premium                 só vira 1 pelo webhook
  plano                   nerd | stalker_do_tomhanks
  stripe_customer_id      cus_...
  stripe_subscription_id  sub_...
```

Não existe coluna de número, CVV ou validade. Esses dados nem passam pelo backend.

### O fluxo
```
Navegador ──POST /premium/checkout {plano}──▶ Catálogo ──cria Checkout Session──▶ Stripe
    ◀──────────────── { checkout_url } ─────────┘
    │
    └──redireciona──▶ checkout.stripe.com (cartão digitado AQUI)
                         │                         │
         volta pro site  │                         │ assíncrono, por outro caminho:
  /app/planos?checkout=  │                         ▼
         sucesso         │      POST /premium/webhook (assinado) ──▶ Catálogo
                         │                                            │ 1. valida a assinatura
                         ▼                                            │ 2. PUT /internal/users/{id}/role ──▶ auth-service
              front pergunta GET /premium/status                      │ 3. grava a assinatura no MySQL
              até o plano aparecer, aí POST /auth/refresh             ▼
              (token novo com o papel novo)                    usuario vira nerd
```

1. **`POST /premium/checkout`** (`app/routers/premium.py`) cria a Checkout Session com `client_reference_id = id do JWT` e `metadata.plano`. O Stripe devolve esses dois intactos no webhook, e é assim que o catálogo sabe quem pagou e o quê. A rota devolve a URL em vez de um `302`, porque a SPA se autentica por header `Bearer`, e um redirect do servidor não levaria o token; quem redireciona é o front.
   - Só vende plano **acima** do papel atual. Mesmo plano, plano abaixo ou admin recebem `409`.
   - Cinéfilo não está à venda: pedir esse plano dá `422`.
2. A **volta do navegador** (`?checkout=sucesso`) **não ativa nada**: essa URL qualquer um digita. A tela só espera.
3. O **webhook** (`POST /premium/webhook`) é a única coisa que ativa um plano. Ele chega de forma assíncrona, pode vir antes ou depois do navegador voltar, e por isso o front pergunta `GET /premium/status` a cada 2 s.

### Validação da assinatura do webhook
A rota é pública e não tem JWT, porque quem chama é o Stripe. Sem validação, qualquer um daria um `curl` com um JSON inventado e virava Stalker de graça. Então:
- O Stripe assina cada chamada no cabeçalho `Stripe-Signature`: um **HMAC-SHA256 do corpo bruto** com o segredo do endpoint (`whsec_...`), que só o Stripe e o servidor conhecem, mais um **timestamp**.
- `pagamentos.validar_webhook` confere a assinatura (`stripe.WebhookSignature.verify_header`) sobre os **bytes exatos** recebidos. A rota é `async` só pra ler `await request.body()`: se o FastAPI parseasse e reserializasse o JSON, a assinatura não bateria.
- São recusados com `400`, sem tocar no banco:
  - sem cabeçalho de assinatura;
  - assinado com outro segredo;
  - corpo alterado depois de assinado;
  - evento com mais de 5 minutos (reenvio de um evento antigo capturado).

  Cada caso tem teste em `tests/test_premium_webhook.py`.
- **Idempotente:** o Stripe reenvia o evento se não receber `2xx`, e processar duas vezes dá no mesmo resultado.

### Trocar o papel: catálogo → auth-service
Quem é dono da tabela `usuarios` continua sendo só o `auth-service`. O webhook chama uma rota **interna** nova, `PUT /internal/users/{id}/role`, protegida por um **token de serviço**:
- é assinado com o mesmo `JWT_SECRET`, mas tem `servico: "catalogo"` e **não tem `sub`**, e vale 1 minuto;
- sem `sub`, ele **não serve como login de usuário** (o auth-service exige `sub`);
- um token de usuário **não serve na rota interna** (não tem `servico`);
- nem o catálogo repassa `/internal/*` pra fora.

A ordem importa: primeiro o papel, depois a assinatura no MySQL. Se o auth-service estiver fora, o webhook responde `502`, nada é gravado e o Stripe **reenvia o evento mais tarde**. O pagamento não se perde.

Outros detalhes:
- **Subir de plano** (Nerd → Stalker): a assinatura antiga é cancelada no Stripe pra ninguém pagar dois planos.
- **Cancelamento** (`customer.subscription.deleted`): volta pra `cinefilo`.
- **Admin** nunca é rebaixado por plano.

### O papel mora no JWT: `POST /auth/refresh`
O papel viaja dentro do token (Padrão B da atividade 4). Logo depois do pagamento, o banco já diz `nerd`, mas o token guardado no navegador ainda diz `cinefilo`. Por isso o `auth-service` ganhou `POST /auth/refresh`, que reemite o token com o papel atual do banco. O front chama essa rota assim que o webhook confirma, e o menu libera Favoritos e Comentários na hora, sem relogar.

Esse é o preço conhecido do Padrão B: num **cancelamento**, um token antigo continua dizendo o papel pago até expirar (`JWT_EXPIRE_MINUTES`).

### Configurar o Stripe
1. Conta gratuita no Stripe, sempre em **modo de teste** (sandbox). Crie dois produtos com preço recorrente mensal em BRL: Nerd e Stalker do Tom Hanks.
2. Preencha `STRIPE_SECRET_KEY` (`sk_test_...`), `STRIPE_PRICE_NERD` e `STRIPE_PRICE_STALKER` (`price_...`) no `.env`.
3. **Webhook em desenvolvimento:** o Stripe não alcança `localhost`, então o [Stripe CLI](https://docs.stripe.com/stripe-cli) faz o túnel:
   ```bash
   stripe login
   stripe listen --forward-to localhost:8000/premium/webhook \
     --events checkout.session.completed,customer.subscription.deleted
   ```
   O `whsec_...` que ele mostra vai em `STRIPE_WEBHOOK_SECRET`.
4. **Webhook em produção:** endpoint criado no painel (*Developers → Webhooks*) apontando pra `https://<domínio>/premium/webhook`, com os mesmos dois eventos. O segredo de assinatura dele, que é outro, vai nas variáveis da stack no Portainer.
5. Pagar com o cartão de teste `4242 4242 4242 4242`, qualquer validade futura e qualquer CVC.

Sem as chaves, a venda fica desligada (`503`) e o resto sobe normal. É assim que o CI roda.

## CI/CD (GitHub Actions, atividade extra)

Até a atividade 6, todo deploy era manual: buildar a imagem no Mac, publicar no Docker Hub, trocar a tag no Portainer e torcer. Agora o caminho inteiro é um workflow, [`.github/workflows/ci.yml`](../.github/workflows/ci.yml). Cada deploy vira uma execução registrada, amarrada a um commit, que qualquer um pode reler ou refazer.

- **CI (Continuous Integration):** a cada push ou pull request, confere se o código ainda funciona. Se não funcionar, o commit fica marcado como quebrado (❌) antes de chegar em qualquer ambiente.
- **CD (Continuous Deployment):** se o CI passou e o push é na `main`, empacota, publica e põe no ar, sem clique.

### O pipeline

```
git push ──▶ Testes (catálogo, log-service) ──┐
             Build das 4 imagens Docker ──────┤──▶ Smoke test ──▶ Publicar no GHCR ──▶ Deploy ──▶ Portainer
                                              │   (stack de pé     sha-xxxxxxx         (commit do    puxa do Git
             qualquer ❌ aqui para tudo ◀─────┘    de verdade)      + latest            robô)         e sobe a tag
```

| Job | O que faz | Quebra o pipeline se... |
|---|---|---|
| Testes — catálogo | `pytest`: os 90 testes (SQLite em memória + mocks) | qualquer teste falhar |
| Testes — log-service | `pytest` com `fakeredis` | idem |
| Build — api / auth-service / log-service / garage | `docker build` das 4 imagens. A do catálogo também compila o Angular | um Dockerfile ou o front não compilar |
| Smoke test — stack de pé | Sobe a stack **inteira** com `docker compose` e um MySQL descartável, roda as migrations do zero e executa [`scripts/smoke-test.sh`](../scripts/smoke-test.sh): cadastro, **login (200; senha errada, 401)**, upload de foto pro Garage, URL pré-assinada, `403` no perfil alheio, eventos no log de auditoria. Sem mock nenhum | qualquer verificação falhar |
| Publicar — ×4 | Só se **todos** os jobs acima passaram e é push na `main`: publica as 4 imagens no GHCR | — |
| Deploy | Reescreve as tags do `docker-compose.portainer.yml` pra `sha-<commit>` e faz um commit automático `deploy: sha-xxxxxxx [skip ci]` | — |

Pull request e push em outra branch rodam só a parte de CI: nada é publicado nem vai pro ar.

### Tag rastreável

As imagens ficam no **GitHub Container Registry**, ligadas a este repositório: `ghcr.io/leonardoricci-tsi/api-filmes`, `api-filmes-auth`, `api-filmes-log` e `api-filmes-garage`. Cada publicação recebe duas tags:

- `sha-xxxxxxx`: os 7 primeiros caracteres do commit. **É essa que roda em produção**, e com ela dá pra saber exatamente qual código está no ar (`git show xxxxxxx`).
- `latest`: a mais recente, por conveniência. Produção nunca usa.

**Rollback** é apontar pra uma tag anterior: reverter o commit `deploy: sha-...` (ou editar as tags pra um `sha-` antigo) e dar push. O Portainer volta pra aquela versão do mesmo jeito que subiu a nova.

### Deploy automático (GitOps)

O workflow **nunca acessa o servidor**. Ele só registra no repositório *qual* versão deve estar no ar, e o servidor segue o repositório:

1. O job **Deploy** troca as tags do [`docker-compose.portainer.yml`](../docker-compose.portainer.yml) pra `sha-<commit>` e faz o commit automático, como `github-actions[bot]`. Esse commit não dispara outro CI: push feito com o `GITHUB_TOKEN` não gera run novo, e o `[skip ci]` reforça.
2. A stack no Portainer (`api-tom-hanks-leonardo`) é criada **a partir deste repositório** (*Build method: Repository*, compose `docker-compose.portainer.yml`, branch `main`) com **GitOps updates** ligado: o Portainer consulta o repositório periodicamente (*polling*), percebe o commit do robô e recria os containers com as tags novas.
3. Opcional: se o secret `PORTAINER_WEBHOOK_URL` estiver configurado no GitHub, o job também chama o webhook da stack, e o deploy acontece na hora, sem esperar o próximo polling.

**Pendências / limites conhecidos:**
- Entre o fim do pipeline e o container novo no ar, passa até um intervalo de polling do Portainer. Com o webhook configurado, esse atraso some.
- **Migrations não rodam no pipeline de produção.** O smoke test prova, a cada push, que elas montam o banco do zero, mas aplicá-las no MySQL de produção continua manual (`docker compose run --rm migrate` / `migrate-auth`). Automatizar isso exigiria dar ao GitHub acesso ao banco de produção, que é justamente o que o GitOps evita.

### Segredos: onde cada um vive (sem revelar nenhum)

Regra desde a atividade 2: credencial nunca vai pro repositório nem pra dentro da imagem. Nenhum YAML, Dockerfile ou imagem deste repositório tem senha, chave ou token (o `.env` está no `.gitignore` e no `.dockerignore` de cada serviço).

| Onde | Quais | Como entram |
|---|---|---|
| **Portainer** (variáveis de ambiente da stack) | `DATABASE_URL`, `JWT_SECRET`, `TMDB_API_KEY`, `SMTP_USER`/`SMTP_PASSWORD` (e demais `SMTP_*`), `GARAGE_RPC_SECRET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_PUBLIC_URL`, `CATALOG_PUBLIC_URL` | Cadastradas na tela da stack; o `docker-compose.portainer.yml` só referencia `${NOME}` |
| **GitHub Secrets** | `PORTAINER_WEBHOOK_URL` (opcional: quem tem essa URL força um redeploy) | *Settings → Secrets and variables → Actions*, lido como `${{ secrets.PORTAINER_WEBHOOK_URL }}` |
| **Automático, por run** | `GITHUB_TOKEN`, que publica no GHCR e faz o commit de deploy | Criado pelo próprio Actions a cada run, expira no fim dele e vale só pra este repositório. Não existe senha de registry guardada em lugar nenhum |
| **Descartáveis do smoke test** | Senha do MySQL temporário, `JWT_SECRET`, chaves do Garage | Gerados com `openssl rand` **dentro do run** e jogados fora com a stack. Não existem antes nem depois |
| **Testes** | Valores obviamente falsos (`teste-jwt-secret-fake`...) | Definidos no [`tests/conftest.py`](../tests/conftest.py). Os testes nunca leem o `.env` de quem roda |

## Observabilidade (health checks e métricas, atividade extra)

Um sistema que você não consegue enxergar por dentro é um sistema que você torce pra continuar funcionando. Dos três pilares da observabilidade, o projeto agora tem dois:

| Pilar | Responde | Onde está |
|---|---|---|
| **Logs** | *o que aconteceu?* ("usuário X fez Y às Z") | Atividade 5: `log-service` + Redis Streams |
| **Métricas** | *como está agora e pra onde está indo?* (req/min, latência, taxa de erro) | Esta atividade: `/metrics` + Prometheus + Grafana |
| Traces | *por onde a requisição passou?* (o caminho entre serviços) | Fora do escopo. Seria OpenTelemetry |

### `/health`: dois tipos de "estou bem"

Cada serviço (catálogo, auth-service, log-service) tem dois endpoints, sem login, porque quem chama é o Docker, não um usuário:

- **`GET /health/live`** (*liveness*): o processo está de pé e respondendo? Não testa mais nada, de propósito. Se isso falhar, reiniciar o container resolve.
- **`GET /health`** (*readiness*): eu consigo **atender de verdade**? Testa cada dependência real e devolve **`503`** se uma **crítica** estiver fora. Nesse caso reiniciar não adianta (reiniciar não faz o banco voltar): o certo é parar de mandar tráfego.

Um `/health` que sempre devolve `200` é pior que nenhum: o container parece "no ar" e fica devolvendo erro pra todo usuário, em silêncio. Por isso a resposta sempre lista cada checagem, com o tempo de cada uma:

```json
{"status": "degraded", "checagens": {
  "mysql":        {"status": "ok",   "critica": true,  "ms": 297},
  "auth-service": {"status": "ok",   "critica": false, "ms": 13},
  "log-service":  {"status": "ok",   "critica": false, "ms": 12},
  "garage":       {"status": "fail", "critica": false, "ms": 5, "erro": "StorageUnavailable"}}}
```

| Serviço | Dependência **crítica** (fora → `503`, `fail`) | Não crítica (fora → `200`, `degraded`) |
|---|---|---|
| Catálogo | MySQL (`SELECT 1`) | auth-service, log-service, Garage (`HEAD` no bucket) |
| auth-service | MySQL (`SELECT 1`) | log-service |
| log-service | Redis (`PING`) | — |

- **Por que só o MySQL é crítico no catálogo:** sem o Garage, só as fotos param. O log-service já é *fire-and-forget* desde a atividade 5. Sem o auth-service, quem já tem token continua usando, porque o JWT é verificado localmente. Tirar o catálogo inteiro do ar por qualquer uma dessas derrubaria junto tudo o que ainda funciona.
- **Sem falha em cascata:** quando a dependência é outro serviço, pergunta só o `/health/live` dele, nunca o `/health` completo. Senão uma queda do MySQL apareceria no health de todo mundo. Com o Redis fora, só o log-service fica `fail`; o catálogo continua `ok`.

### `HEALTHCHECK` do Docker

Todos os containers do `docker-compose.yml` (e do `docker-compose.portainer.yml`, de produção) têm `healthcheck`, então o `docker ps` e o Portainer mostram `(healthy)`/`(unhealthy)`:

| Container | Checagem | Fica `unhealthy` quando |
|---|---|---|
| api, auth-service, log-service | `GET /health` via Python (`urllib`): as imagens *slim* não têm `curl`, e o `urlopen` já dá erro no `503` | uma dependência crítica cai |
| redis | `redis-cli ping` | o Redis não responde |
| garage | `/garage status`: a imagem não tem shell nem `curl`, só o binário | o nó não responde |
| prometheus, grafana | `wget` no endpoint de saúde de cada um | idem |

Checagem a cada 10–15s, e `unhealthy` só depois de **3 falhas seguidas** (~45s), pra uma oscilação de um segundo não virar alarme. Quando a dependência volta, a próxima checagem já devolve `healthy`. De quebra, o smoke test do CI usa `docker compose up --wait`, que agora espera **todos** os containers ficarem `healthy` antes de testar.

### `/metrics` (Prometheus)

Os três serviços são instrumentados com `prometheus-fastapi-instrumentator`:

- `http_requests_total{handler, method, status}`: requisições por **rota** e **código de status**. A rota entra como template (`/profiles/{usuario_id}`), nunca com o id de verdade, senão cada usuário viraria uma série nova. O status é o exato (`403`, `415`), não agrupado em `4xx`.
- `http_request_duration_seconds`: **histograma de latência** por rota, com faixas de 10ms a 5s. As faixas padrão (0,1s, 0,5s, 1s) davam um p95 inútil, já que só o round-trip até o MySQL remoto leva de 0,3 a 0,7s.
- O `/health` fica **fora** da contagem: o `HEALTHCHECK` chama a cada 15s e inflaria req/min com tráfego que não é de usuário.

**O `/metrics` fica numa porta interna separada (`9100`), não publicada.** O catálogo é o único serviço público, e um `/metrics` na porta dele ficaria aberto na internet mostrando rotas, volume de tráfego e taxa de erro. Quem lê é o Prometheus, de dentro da rede do Docker (`api:9100`, `auth-service:9100`, `log-service:9100`). Em produção, `https://leonardo-oliveira-isw055.lapps.studio/metrics` devolve `404`.

### Prometheus + Grafana (bônus)

`docker compose up` sobe também:

- **Prometheus** ([`observabilidade/prometheus/prometheus.yml`](../observabilidade/prometheus/prometheus.yml)): coleta os 3 serviços a cada 15s e guarda 7 dias. Os alvos ficam em http://localhost:9090/targets.
- **Grafana** (http://localhost:3000): fonte de dados e painel vêm **prontos do repositório** ([`observabilidade/grafana/`](../observabilidade/grafana/)), sem configurar nada pela interface. O painel abre sem login, só leitura; editar exige o admin, com a senha vinda do `.env` (`GRAFANA_ADMIN_PASSWORD`).

As duas portas ficam presas no `127.0.0.1` da máquina: não abrem pra rede. O painel *API Filmes — saúde e métricas* tem:

| Painel | Query (PromQL) |
|---|---|
| Serviços no ar | `up` |
| Requisições por minuto | `sum by (job) (rate(http_requests_total[$__rate_interval])) * 60` |
| Taxa de erro (4xx+5xx e só 5xx) | `rate` dos `status=~"4..\|5.."` ÷ `rate` do total, por serviço |
| Latência p95 (por serviço e por rota do catálogo) | `histogram_quantile(0.95, sum by (job, le) (rate(http_request_duration_seconds_bucket[...])))` |
| Requisições por rota e status | `sum by (job, handler, method, status) (increase(http_requests_total[$__range]))` |

**Só no compose local, não em produção:** o servidor da disciplina expõe só o domínio do catálogo, então o Grafana não teria como ser acessado de fora, e dois containers a mais pesariam no servidor compartilhado. Em produção ficam os `/health` e os `HEALTHCHECK`, que é o que o Portainer mostra.

## Recuperação de senha (esqueci minha senha)

1. `POST /auth/forgot-password` com o e-mail — sempre responde a mesma mensagem genérica, exista ou não o e-mail cadastrado (evita que alguém descubra quais e-mails têm conta testando um por um).
2. Se o e-mail existir, o `auth-service` gera um token aleatório (`secrets.token_urlsafe(32)`), grava na tabela `reset_tokens` com `expira_em = agora + 30 minutos` e `usado = false`, e envia por e-mail um link `.../redefinir-senha?token=...`.
3. `POST /auth/reset-password` com o token e a nova senha — o `auth-service` só troca a senha se o token existir, não estiver expirado e não tiver sido usado ainda; qualquer uma dessas falhas recusa a troca com `400`, sem dizer qual delas falhou.
4. Um token só pode ser usado uma vez: depois de trocar a senha, ele é marcado `usado = true` e uma segunda tentativa com o mesmo token é recusada.

Telas no frontend: `/esqueci-senha` (pedir o link) e `/redefinir-senha?token=...` (definir a nova senha, é a rota pra onde aponta o link do e-mail).

## Como rodar localmente

### 1. Pré-requisitos
- Python 3.11+
- Node.js 20+ (Angular CLI 21 exige Node `^20.19 || ^22.12 || >=24.0`)
- Um MySQL acessível (host, usuário, senha e um banco já criados)
- Um Redis acessível (só se for rodar o `log-service` fora do Docker — pela alternativa do Docker Compose, no passo 8, já vem incluso)
- Uma chave de API do TMDB (https://www.themoviedb.org/settings/api)
- Uma conta no [Mailtrap](https://mailtrap.io) (grátis) — Email Testing → Inboxes → sua inbox → aba **SMTP Settings**, pra pegar `SMTP_USER`/`SMTP_PASSWORD`

### 2. Ambiente virtual e dependências
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -r auth-service/requirements.txt

# log-service é um projeto Python à parte (dependências próprias — fakeredis
# nos testes, sem SQLAlchemy/Alembic), por isso tem seu próprio .venv:
python3 -m venv log-service/.venv
log-service/.venv/bin/pip install -r log-service/requirements.txt
```

### 3. Configurar variáveis de ambiente
Copie `.env.example` para `.env` e preencha com valores reais (o catálogo e o `auth-service` compartilham o mesmo `.env`):
```bash
cp .env.example .env
```
```
DATABASE_URL=mysql+pymysql://usuario:senha@host:3306/nome_do_banco
TMDB_API_KEY=sua_chave_do_tmdb
JWT_SECRET=um_valor_aleatorio_forte
JWT_EXPIRE_MINUTES=60
AUTH_SERVICE_URL=http://localhost:8001   # só pra rodar fora do Docker
LOG_SERVICE_URL=http://localhost:8002    # idem
REDIS_URL=redis://localhost:6379/0       # idem
SMTP_HOST=sandbox.smtp.mailtrap.io
SMTP_PORT=587
SMTP_USER=usuario_do_mailtrap
SMTP_PASSWORD=senha_do_mailtrap

# Garage (atividade 6) — gere com os comandos do .env.example
GARAGE_RPC_SECRET=...                    # openssl rand -hex 32
S3_ACCESS_KEY=GK...                      # echo "GK$(openssl rand -hex 16)"
S3_SECRET_KEY=...                        # openssl rand -hex 32
S3_ENDPOINT_URL=http://localhost:3900    # só pra rodar fora do Docker
S3_PUBLIC_URL=http://localhost:8000      # o endereço pelo qual o site é acessado

# Grafana (observabilidade) — openssl rand -hex 16
GRAFANA_ADMIN_PASSWORD=...

# Stripe (atividade 7) — sempre modo de teste
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PRICE_NERD=price_...
STRIPE_PRICE_STALKER=price_...
STRIPE_WEBHOOK_SECRET=whsec_...          # o do `stripe listen`, em dev
CATALOG_PUBLIC_URL=http://localhost:8000 # pra onde o Stripe devolve o navegador
```

### 4. Rodar as migrations (catálogo e auth-service)
```bash
.venv/bin/alembic upgrade head
cd auth-service && ../.venv/bin/alembic upgrade head && cd ..
```
O catálogo cria `favoritos`, `comentarios` e `perfis`; o `auth-service` cria/altera `usuarios` (`role`) e `reset_tokens` — cada um com sua própria tabela de versão do Alembic (`alembic_version` e `alembic_version_auth`), já que dividem o mesmo schema MySQL.

### 5. Instalar as dependências do frontend
```bash
cd frontend && npm install
```

### 6. Subir em desenvolvimento (5 terminais)
```bash
# Terminal 1 — Redis (só o log-service precisa) e Garage (fotos de perfil)
docker run --rm -p 6379:6379 redis:7-alpine
docker build -t api-filmes-garage ./garage && docker run --rm -p 3900:3900 \
  -e GARAGE_RPC_SECRET -e GARAGE_DEFAULT_ACCESS_KEY="$S3_ACCESS_KEY" \
  -e GARAGE_DEFAULT_SECRET_KEY="$S3_SECRET_KEY" -e GARAGE_DEFAULT_BUCKET=api-filmes-perfis \
  api-filmes-garage   # com as variáveis do .env exportadas no shell

# Terminal 2 — log-service (venv próprio, ver passo 2)
cd log-service
set -a && source ../.env && set +a
.venv/bin/uvicorn app.main:app --reload --port 8002

# Terminal 3 — catálogo
.venv/bin/uvicorn app.main:app --reload --reload-exclude "$(pwd)/.venv"

# Terminal 4 — auth-service (as variáveis do .env da raiz precisam estar no ambiente)
cd auth-service
set -a && source ../.env && set +a
../.venv/bin/uvicorn app.main:app --reload --port 8001

# Terminal 5 — Angular (proxy encaminha /auth,/movies,/favorites,/comments pra :8000)
cd frontend && npm start
```
> O `--reload-exclude "$(pwd)/.venv"` é necessário porque o uvicorn sempre observa o diretório atual além do código do app — sem isso, qualquer instalação/atualização de pacote no `.venv` dispara reloads em loop e trava as requisições.
> Rodando assim (sem Docker), catálogo e `auth-service` precisam de `AUTH_SERVICE_URL=http://localhost:8001` e `LOG_SERVICE_URL=http://localhost:8002` no `.env` — os padrões `http://auth-service:8001`/`http://log-service:8002` só resolvem dentro da rede do Docker.
- Abrir **http://localhost:4200** (Angular com hot-reload, chamando a API via proxy)
- Catálogo sozinho: http://127.0.0.1:8000 — Docs interativas (Swagger): http://127.0.0.1:8000/docs
- `auth-service` nunca é chamado direto pelo navegador — só o catálogo fala com ele.

### 7. Build de produção (um único servidor pro catálogo)
```bash
cd frontend && npm run build   # gera os arquivos em app/static
cd .. && .venv/bin/uvicorn app.main:app
```
- Tudo servido em **http://127.0.0.1:8000** (API + frontend juntos, como o `angular.json` já aponta `outputPath` pra `app/static`)

### 8. Alternativa: rodar tudo com Docker Compose (recomendado)
```bash
docker compose up --build
```
- Sobe os containers na mesma rede (`catalog-net`): `api`, `auth-service`, `log-service`, `redis`, `garage`, e os de observabilidade, `prometheus` e `grafana`. Só o `api` publica porta pra rede (`:8000`); Grafana (`:3000`) e Prometheus (`:9090`) ficam presos no `127.0.0.1`. O `garage` cria sozinho a chave de acesso e o bucket no primeiro boot, a partir de `S3_ACCESS_KEY`/`S3_SECRET_KEY`/`S3_BUCKET` do `.env`.
- Rodar as migrations do catálogo e do `auth-service` (perfil `tools`, não sobe com o `up` normal — o `log-service` não tem migration, não guarda nada em SQL):
  ```bash
  docker compose run --rm migrate
  docker compose run --rm migrate-auth
  ```
- Confirmar que `auth-service`, `log-service`, `redis` e `garage` não têm porta publicada:
  ```bash
  docker compose ps   # só o api publica pra rede (0.0.0.0:8000); prometheus e grafana só em 127.0.0.1
  ```

### 9. Rodar os testes
```bash
.venv/bin/pytest -v                              # catálogo (raiz)
cd log-service && .venv/bin/python -m pytest -v  # log-service — .venv próprio (passo 2)
```
Os testes do catálogo usam SQLite em memória (não tocam no MySQL configurado em `.env`), mockam as chamadas à TMDB e mockam as respostas do `auth-service`/`log-service` (`respx`) — rodam offline. Incluem os testes críticos de isolamento entre usuários: um usuário A não consegue ler, editar ou deletar um favorito/comentário do usuário B mesmo sabendo o ID do recurso (a API responde `404`, nunca `403`, para não vazar a existência do recurso).

A suíte do catálogo não depende do `.env` de quem roda: o `tests/conftest.py` define o próprio ambiente antes de importar o app (segredos falsos, serviços internos numa porta local fechada). Por isso ela roda igual na sua máquina e no GitHub Actions, onde não existe `.env`.

Smoke test da stack inteira (o mesmo do CI), com a stack de pé via `docker compose up`:
```bash
scripts/smoke-test.sh http://localhost:8000
```

Os testes do `log-service` usam `fakeredis` (Redis em memória, sem precisar de um Redis de verdade rodando) — têm seu próprio `.venv` e `pytest.ini`, por isso rodam à parte (cada serviço é um projeto Python independente).

## Endpoints

### Catálogo (público, `http://localhost:8000`)
| Método | Rota | Auth | Descrição |
|---|---|---|---|
| POST | `/auth/register` | não | Proxy pro `auth-service` — cadastra usuário, retorna JWT |
| POST | `/auth/login` | não | Proxy pro `auth-service` — login, retorna JWT |
| GET | `/auth/me` | sim | Proxy pro `auth-service` — dados do usuário logado |
| POST | `/auth/forgot-password` | não | Proxy pro `auth-service` — pede o link de redefinição por e-mail |
| POST | `/auth/reset-password` | não | Proxy pro `auth-service` — troca a senha usando o token do e-mail |
| GET | `/movies` | não | Lista filmes do Tom Hanks (dados ao vivo da TMDB, com sinopse; cache em memória de 5 min) |
| POST | `/favorites` | sim (nerd+) | Favorita um filme |
| GET | `/favorites` | sim (nerd+) | Lista favoritos do usuário logado |
| DELETE | `/favorites/{id}` | sim (nerd+) | Remove um favorito do usuário logado |
| POST | `/comments` | sim (nerd+) | Comenta um filme (envia `titulo` do filme junto) |
| GET | `/comments` | sim (nerd+) | Lista **todos** os comentários do usuário logado |
| GET | `/comments?tmdb_movie_id=` | sim (nerd+) | Lista comentários do usuário logado sobre um filme específico |
| DELETE | `/comments/{id}` | sim (nerd+) | Remove um comentário do usuário logado |
| GET | `/quiz/pixelado` | sim (stalker+) | Sorteia um filme, devolve o pôster pixelado + 4 opções de título |
| POST | `/quiz/pixelado/resposta` | sim (stalker+) | Confere o palpite — checagem sempre no servidor |
| GET | `/admin/comments` | sim (admin) | Lista comentários de **todos** os usuários (moderação) |
| DELETE | `/admin/comments/{id}` | sim (admin) | Remove o comentário de qualquer usuário |
| GET | `/admin/favorites` | sim (admin) | Lista favoritos de **todos** os usuários (moderação) |
| DELETE | `/admin/favorites/{id}` | sim (admin) | Remove o favorito de qualquer usuário |
| GET | `/auth/admin/users` | sim (admin) | Proxy pro `auth-service` — lista todos os usuários cadastrados |
| PATCH | `/auth/admin/users/{id}/role` | sim (admin) | Proxy pro `auth-service` — promove/rebaixa o papel de um usuário |
| GET | `/health` | não | Readiness: testa MySQL, auth-service, log-service e Garage. `503` se o MySQL estiver fora ([Observabilidade](#observabilidade-health-checks-e-métricas-atividade-extra)) |
| GET | `/health/live` | não | Liveness: só confirma que o processo responde |
| POST | `/auth/logout` | sim | Não invalida nada no servidor (JWT é stateless) — só registra o evento de auditoria |
| GET | `/admin/logs` | sim (admin) | Proxy pro `log-service` — últimos N eventos de auditoria (atividade 5), mais recente primeiro |
| GET | `/profiles/{id}` | sim | Perfil de qualquer usuário: nome, bio, `foto_url` (pré-assinada, 15 min), favoritos, `eh_meu` |
| PATCH | `/profiles/{id}` | sim (só o dono) | Edita a bio — `403` se `{id}` não for o do token |
| POST | `/profiles/{id}/foto` | sim (só o dono) | Upload da foto (`multipart`, campo `arquivo`; JPEG/PNG/WEBP, até 2 MB) — `403`, `413`, `415`, `502` |
| POST | `/premium/checkout` | sim | Corpo `{"plano": "nerd" \| "stalker_do_tomhanks"}`: cria a Checkout Session do Stripe e devolve `checkout_url`. `409` se já tiver o plano ou um acima, `503` sem Stripe configurado |
| GET | `/premium/status` | sim | `{premium, plano}` do usuário logado (o front consulta na volta do checkout) |
| POST | `/premium/webhook` | assinatura `Stripe-Signature` | Chamado pelo Stripe: ativa ou encerra o plano e troca o papel. `400` com assinatura inválida |
| POST | `/auth/refresh` | sim | Proxy pro `auth-service`: token novo com o papel atual (depois de um pagamento) |
| GET | `/api-filmes-perfis/{chave}?X-Amz-...` | assinatura na URL | Não é rota da API (fora do Swagger): repassa a URL pré-assinada pro Garage, que valida a assinatura |

Autenticação via header `Authorization: Bearer <token>`. "nerd+" = `nerd`, `stalker_do_tomhanks` ou `admin`; "stalker+" = `stalker_do_tomhanks` ou `admin` — a escada é cumulativa (veja [Autorização (RBAC)](#autorização-rbac-atividade-4)).

### auth-service (interno, sem acesso externo)
Só respondem pra chamadas vindas do catálogo, dentro da rede `catalog-net`: `/auth/register`, `/auth/login`, `/auth/me`, `/auth/forgot-password`, `/auth/reset-password`, `/auth/admin/users`, `/auth/admin/users/{id}/role`, `/auth/users/{id}` (só `id` e `nome`, pra página de perfil), `/auth/refresh` e `/internal/users/{id}/role` (troca de papel pelo plano pago; só aceita o token de serviço do catálogo, ver [Planos pagos](#trocar-o-papel-catálogo--auth-service)).

### log-service (interno, sem acesso externo)
Só respondem pra chamadas vindas do catálogo ou do `auth-service`, dentro da rede `catalog-net`:
| Método | Rota | Auth | Descrição |
|---|---|---|---|
| POST | `/logs` | não (interno) | Grava um evento no Redis Stream — sem autenticação própria porque só é alcançável de dentro da rede, chamado depois que o catálogo/auth-service já identificaram o usuário |
| GET | `/logs?limit=` | sim (admin) | Últimos N eventos, mais recente primeiro — é essa rota que o catálogo repassa em `GET /admin/logs` |

## Documentação da API (Swagger/OpenAPI)

Os três serviços são FastAPI, então o Swagger UI e a spec OpenAPI já existem de graça — nenhuma biblioteca extra, nenhuma anotação manual pra descrever rota/parâmetro/formato de resposta: o FastAPI gera tudo isso a partir dos `response_model` e schemas Pydantic que o código já tinha antes desta atividade.

**O que essa atividade acrescentou de verdade:** documentar os *erros*. Por padrão o FastAPI só descreve o caminho de sucesso (e o `422` automático de validação) — todo `HTTPException` que uma rota levanta (`401`, `403`, `404`, `409`, `502`...) aparecia como *"Undocumented"* no Swagger até alguém clicar em "Try it out" e ver na marra. Cada rota autenticada ou que pode falhar agora declara `responses=` com descrição + exemplo de payload pro erro real que ela levanta — nada inventado, os textos batem com o `detail` que o código manda (`app/openapi_responses.py` no catálogo, equivalente em `auth-service/` e `log-service/`, reaproveitados entre rotas com o mesmo tipo de erro pra não duplicar o mesmo dicionário 20 vezes).

**Onde ver:**
| Serviço | Swagger UI | Spec OpenAPI |
|---|---|---|
| Catálogo | público — https://leonardo-oliveira-isw055.lapps.studio/docs (ou `http://localhost:8000/docs` local) | `GET /openapi.json` no mesmo host |
| `auth-service` | sem porta publicada, não dá pra acessar de fora | exportada em [`docs/openapi/auth-service.json`](openapi/auth-service.json) — cole em [editor.swagger.io](https://editor.swagger.io) pra visualizar, ou rode local (passo 6 de "Como rodar localmente") e acesse `http://localhost:8001/docs` |
| `log-service` | sem porta publicada, não dá pra acessar de fora | exportada em [`docs/openapi/log-service.json`](openapi/log-service.json) — mesma ideia, ou local em `http://localhost:8002/docs` |

`auth-service` e `log-service` ficarem sem Swagger público não é uma limitação desta atividade — é a mesma decisão de arquitetura de sempre (nenhum dos dois tem porta publicada pro host, [ver Arquitetura](#arquitetura)); a spec exportada é a alternativa que o próprio enunciado prevê pra esse caso ("o arquivo openapi.yaml/.json no repositório também vale"). Pra regenerar depois de mexer numa rota:
```bash
# catálogo
.venv/bin/python -c "import json; from app.main import app; json.dump(app.openapi(), open('docs/openapi/catalogo.json', 'w'), ensure_ascii=False, indent=2)"

# auth-service (precisa das env vars mínimas pro Settings não reclamar)
cd auth-service && ../.venv/bin/python -c "
import os, json
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:'); os.environ.setdefault('JWT_SECRET', 'x')
os.environ.setdefault('SMTP_USER', 'x'); os.environ.setdefault('SMTP_PASSWORD', 'x')
from app.main import app
json.dump(app.openapi(), open('../docs/openapi/auth-service.json', 'w'), ensure_ascii=False, indent=2)
"

# log-service
cd log-service && .venv/bin/python -c "
import os, json
os.environ.setdefault('JWT_SECRET', 'x')
from app.main import app
json.dump(app.openapi(), open('../docs/openapi/log-service.json', 'w'), ensure_ascii=False, indent=2)
"
```

## Estrutura do projeto
```
app/                    # catálogo
  models/       # SQLAlchemy declarative models (favoritos, comentarios, perfis)
  schemas/      # Pydantic (request/response)
  auth/         # verificação local do JWT (get_current_user, require_papel_minimo, require_admin)
  routers/      # rotas da API: quiz.py (pixelado, stalker+), admin.py (moderação de comentários e favoritos),
                #   auth.py (proxy de /auth/* e /auth/admin/* pro auth-service), comments/favorites (nerd+),
                #   profiles.py (perfil + upload de foto, só o dono edita), storage_proxy.py (repasse da URL
                #   pré-assinada pro Garage), premium.py (checkout, status e webhook do Stripe, atividade 7)
  services/     # cliente HTTP do auth-service (auth_client.py), do log-service (log_client.py) + cliente da TMDB,
                #   storage.py (Garage via boto3), imagem.py (validação/reencodagem da foto com Pillow),
                #   pagamentos.py (Checkout Session e validação da assinatura do webhook do Stripe)
  openapi_responses.py  # blocos de erro (401/403/404/409/502) reaproveitados no responses= de cada rota
  static/       # build de produção do Angular (gerado por `npm run build`, não editar à mão)
alembic/        # migrations do catálogo
tests/          # pytest (SQLite em memória + mocks da TMDB, do auth-service e do log-service via respx),
                #   test_roles.py cobre o RBAC, test_audit_log.py cobre a auditoria (atividade 5)
auth-service/           # microsserviço de autenticação
  app/
    models/     # Usuario (com role: cinefilo/nerd/stalker_do_tomhanks/admin), ResetToken
    auth/       # hash de senha, emissão/validação de JWT, geração e validação de reset tokens, require_admin
    routers/    # /auth/* (register, login, me), /auth/forgot-password, /auth/reset-password,
                #   /auth/admin/users e /auth/admin/users/{id}/role (admin.py, atividade 4), /auth/refresh,
                #   internal.py (PUT /internal/users/{id}/role, só com token de serviço do catálogo, atividade 7)
    services/   # mailer.py (e-mail de redefinição via SMTP), log_client.py (evento de login/403 pro log-service)
    openapi_responses.py  # mesma ideia do catálogo, blocos de erro pro Swagger
  alembic/      # migrations do auth-service (histórico próprio, alembic_version_auth)
log-service/            # microsserviço de auditoria (atividade 5) — SEM alembic/SQL, só Redis
  app/
    schemas.py  # LogEventIn/LogEventOut (usuario_id, acao, timestamp, ip)
    auth.py     # require_admin — decodifica o mesmo JWT localmente, sem tabela de usuários própria
    redis_client.py  # dependência do FastAPI (troca por fakeredis nos testes)
    routers/logs.py  # POST /logs (XADD) e GET /logs (XREVRANGE, só admin)
  tests/        # pytest com fakeredis — .venv e pytest.ini próprios (projeto Python à parte)
frontend/       # projeto Angular (standalone components)
  src/app/
    core/       # services (auth/movies/favorites/comments), interceptor de JWT, guards de rota
    layout/     # header (avatar + navegação) e app-shell (layout das rotas privadas)
    shared/     # movie-card (usado no catálogo e nos favoritos, com diálogo de comentários)
    features/   # telas: auth/login, auth/register, auth/forgot-password, auth/reset-password, catalog, favorites,
                #   comments, profile (perfil com foto, bio e favoritos), planos (os 3 planos + volta do Stripe)
garage/                 # Dockerfile + garage.toml do object storage (atividade 6), sem segredos
.github/workflows/ci.yml  # pipeline de CI/CD: testes, build, smoke test, publicação no GHCR e deploy
scripts/smoke-test.sh   # smoke test da stack inteira de pé (usado pelo CI)
docker-compose.yml      # os cinco serviços (api, auth-service, log-service, redis, garage) + rede catalog-net
docker-compose.ci.yml   # só pro CI: acrescenta um MySQL descartável pro smoke test
observabilidade/        # Prometheus (alvos de coleta) e Grafana (fonte de dados + painel provisionados)
docker-compose.portainer.yml  # stack de produção; as tags sha-xxxxxxx são atualizadas pelo pipeline
docs/openapi/           # spec OpenAPI exportada de auth-service e log-service (sem porta publicada,
                        #   Swagger UI deles só dá pra ver local — ver "Documentação da API")
```

## Notas de segurança / design
- `poster_path` e sinopse dos filmes nunca são persistidos — sempre vêm ao vivo da TMDB a cada chamada a `/movies`. O único dado de filme salvo no banco é o `tmdb_movie_id` (e, em `favoritos`/`comentarios`, uma cópia do título escolhida pelo usuário no momento de favoritar/comentar — só pra exibição, não é cache do catálogo).
- `usuario_id` nunca vem do corpo da requisição — é sempre extraído do JWT.
- Toda query de favoritos/comentários filtra obrigatoriamente por `usuario_id` do usuário logado (`app/routers/_ownership.py`).
- O JWT é assinado só pelo `auth-service`; o catálogo apenas verifica a assinatura com o `JWT_SECRET` compartilhado — não existe endpoint que aceite `role` ou `usuario_id` vindos do cliente.
- Token de redefinição de senha: aleatório e criptograficamente seguro (`secrets.token_urlsafe`, não um UUID sequencial), expira em 30 minutos, é de uso único, e a mensagem de "esqueci minha senha" nunca revela se o e-mail existe ou não.
- Promover/rebaixar o papel de um usuário é `PATCH /auth/admin/users/{id}/role` — só admin (atividade 4). O **primeiro** admin do sistema, esse sim, precisa ser promovido manualmente no banco (`UPDATE usuarios SET role='admin' WHERE id=...`), já que ninguém nasce admin — é o único bootstrap que não tem endpoint de propósito.
- `npm run build` copia `index.html` para `404.html` em `app/static` (truque padrão do Starlette pra SPA): assim, um refresh direto numa rota do Angular (ex: `/favoritos`) ainda carrega o app em vez de um 404 vazio.
- Auditoria (atividade 5) é fire-and-forget: uma falha no `log-service` (fora do ar, rede interna com problema) nunca derruba a ação real do usuário — favoritar/comentar/logar não podem virar `500` por causa de um serviço que só observa. O custo é a possibilidade (rara) de perder um evento se o `log-service` cair bem na hora; pra essa atividade, não justifica trocar por fila/retry.
- Foto de perfil (atividade 6): tipo conferido pelos bytes, não pelo `Content-Type`; tamanho e dimensão limitados antes de decodificar; reencodada (sem EXIF/GPS); chave gerada pelo servidor; bucket privado, lido só por URL pré-assinada com expiração.
- Pagamento (atividade 7): o cartão nunca passa pelo backend (página hospedada pelo Stripe); o banco guarda só `cus_`/`sub_`. Só o webhook com assinatura HMAC válida (e timestamp de até 5 min) ativa um plano, e a volta do navegador do checkout não ativa nada. A troca de papel no `auth-service` usa um token de serviço sem `sub`, que não serve como login.
- `log-service` não tem tabela de usuários própria — decodifica o mesmo JWT localmente (mesmo `JWT_SECRET`) pra saber quem é admin, igual o catálogo faz pro resto do RBAC.

## Evidências

### Atividade 7 — Planos pagos com Stripe (modo de teste)

Usuário de teste: **Bruno** (id 35), no plano gratuito, assinando o **Nerd**.

**1. Antes de pagar, a ação é negada:** no plano Cinéfilo, favoritar devolve `403` (`Ação exige papel 'nerd' ou superior`) e a tela leva pros planos. O menu só tem "Catálogo".

![Bruno no plano gratuito: favoritar devolve 403](evidencias/planos-1-gratuito-403-favoritar.jpg)

**2. Página de planos** (`/app/planos`): Cinéfilo marcado como "Seu plano"; Nerd e Stalker à venda.

![Página de planos com os três níveis](evidencias/planos-2-pagina-de-planos.jpg)

**3. Checkout hospedado pelo Stripe, em modo de teste** ("Área restrita"): Nerd a R$ 19,90/mês, pago com o cartão de teste `4242 4242 4242 4242`. É uma página do Stripe; o cartão nunca passa pelo nosso backend.

![Checkout do Stripe em modo de teste com o cartão 4242](evidencias/planos-3-checkout-stripe-nerd.jpg)

**4. Pagamento concluído no Stripe:** `Succeeded`, R$ 19,90, •••• 4242, no sandbox. O cliente Bruno Curioso foi criado lá, não aqui.

![Pagamento do plano Nerd com status Succeeded no painel do Stripe](evidencias/planos-7-stripe-pagamento-nerd-sucesso.png)

![Cliente Bruno Curioso no painel do Stripe](evidencias/planos-6-stripe-cliente-bruno.png)

**5. De volta ao site, depois do webhook:** "Pagamento confirmado! Agora você está no plano Nerd". O token foi renovado e o menu já mostra Favoritos e Comentários.

![Página de planos depois da confirmação: Nerd é o plano atual](evidencias/planos-4-pagamento-confirmado-nerd.jpg)

**6. No banco, depois do webhook:** `assinaturas` com `premium = 1`, `plano = nerd` e o `sub_...` do Stripe (nenhum dado de cartão), e o papel em `usuarios` já é `nerd`.

![MySQL: assinatura do Bruno com plano nerd e papel nerd](evidencias/planos-8-mysql-assinatura-e-papel.png)

**7. O benefício funcionando:** a **mesma ação** do print 1 agora devolve `201`, com o botão em "★ Favoritado".

![Bruno no plano Nerd: favoritar funciona](evidencias/planos-5-nerd-201-favoritar.jpg)

### Atividade extra — Observabilidade: health checks e métricas

**1. `docker ps` (Portainer, produção) com tudo no ar:** todos os containers `healthy`.

![Containers da stack no Portainer, todos healthy](evidencias/obs-docker-ps-healthy.png)

**2. Redis derrubado, e o log-service vira `unhealthy` sozinho:** o Redis foi parado (`exited - code 0`) e ninguém tocou no log-service. Depois de 3 checagens seguidas com `503` no `/health` dele, o Docker o marcou como `unhealthy`. Catálogo, auth-service e Garage continuam `healthy`, porque o Redis não é dependência deles. Com o Redis de volta, ele volta a `healthy` na checagem seguinte.

![Com o Redis parado, só o log-service aparece unhealthy](evidencias/obs-docker-ps-redis-fora.png)

**3. Painel no Grafana** (bônus), com a stack local sob tráfego real (smoke test em laço):

![Painel do Grafana: serviços no ar, requisições por minuto, taxa de erro e latência p95](evidencias/obs-grafana-painel.png)

Req/min por serviço; taxa de erro de ~43% no catálogo, sendo ~14% de 5xx: neste ambiente de teste a chave do TMDB era falsa, então o `/movies` devolvia `502`, o que é justamente o que o painel de erro existe pra mostrar. p95 de ~240ms no catálogo e no auth-service (o `bcrypt` do login é lento de propósito) e ~9ms no log-service.

**4. Requisições por serviço, rota, método e status**, a mesma informação do `/metrics` cru, somada no Grafana:

![Tabela do Grafana com requisições por serviço, rota, método e código de status](evidencias/obs-grafana-rotas.png)

### Atividade extra — CI/CD: pipeline verde e produção rodando a tag do commit

**1. Execução real do workflow, toda verde:** [Actions → CI/CD → run 36759550355](https://github.com/leonardoricci-tsi/api_filme_/actions/runs/36759550355) (commit `e424517`). Os 12 jobs passaram: 2 de testes, 4 de build, o smoke test, 4 de publicação no GHCR e o deploy, que gerou o commit automático `deploy: sha-e424517 [skip ci]`.

**2. Produção rodando exatamente a imagem que esse run publicou:** containers da stack `api-tom-hanks-leonardo` no Portainer com as imagens `ghcr.io/leonardoricci-tsi/...:sha-e424517`, a tag do commit, não a `latest`:

![Containers da stack no Portainer rodando as imagens do GHCR com a tag sha-e424517](evidencias/cicd-container-tag-commit.png)

**3. Deploy automático de ponta a ponta, sem clique:** o push do commit `7b185e1` (a documentação desta seção) passou pelo [run 36768320775](https://github.com/leonardoricci-tsi/api_filme_/actions/runs/36768320775), todo verde. O job Deploy fez o commit `deploy: sha-7b185e1 [skip ci]`, e o Portainer, por polling, recriou sozinho os 4 containers com a tag nova, sem ninguém abrir o Portainer. O `redis`, que não mudou, ficou intacto (criado uma hora antes):

![Mesmos containers, agora com a tag sha-7b185e1, recriados automaticamente pelo Portainer](evidencias/cicd-deploy-automatico.png)

### Atividade 6 — Perfil com foto no object storage

**1. `docker-compose.yml` com o object storage adicionado** (Garage, no lugar do MinIO, ver [Por que Garage](#por-que-garage-e-não-minio)):

```yaml
  garage:
    build: ./garage              # dxflrs/garage:v2.3.0 + garage.toml
    environment:
      GARAGE_RPC_SECRET: ${GARAGE_RPC_SECRET}
      GARAGE_DEFAULT_ACCESS_KEY: ${S3_ACCESS_KEY}
      GARAGE_DEFAULT_SECRET_KEY: ${S3_SECRET_KEY}
      GARAGE_DEFAULT_BUCKET: ${S3_BUCKET:-api-filmes-perfis}
    expose:
      - "3900"                   # sem porta publicada: a foto sai pelo domínio do catálogo
    networks:
      - catalog-net
    volumes:
      - garage-meta:/var/lib/garage/meta
      - garage-data:/var/lib/garage/data
```

**2. Perfil com a foto enviada aparecendo de verdade** (servida por URL pré-assinada):

![Página de perfil com foto de upload, bio e filmes favoritos](evidencias/perfil-com-foto.png)

**3. Tentativa recusada de editar o perfil de outro usuário.** Token da Ana (id 34), ID do Bruno (35) na URL, e o corpo ainda tentando reforçar com `"usuario_id": 35`: o backend confere o `{id}` contra o JWT, ignora o corpo e responde `403`. O perfil do Bruno continua intacto, e a tentativa fica no log de auditoria como `acesso_negado:perfil:35`.

![PATCH /profiles/{id de outro usuário} recusado com 403](evidencias/perfil-403-outro-usuario.png)


### Atividade extra — Documentação Swagger/OpenAPI: erro documentado + "Try it out" executado

`GET /admin/comments` chamado por um usuário `nerd` (não-admin), direto no Swagger UI público (https://leonardo-oliveira-isw055.lapps.studio/docs) — antes desta atividade o `403` que essa rota levanta aparecia como *"Undocumented"* no Swagger; agora está descrito, com exemplo de payload, ao lado do `401` e do `200`.

**1. Endpoint expandido, mostrando os erros documentados na tabela "Responses" (ainda sem executar):**

![Tabela de Responses do Swagger mostrando 200, 401 e 403 documentados, cada um com descrição e exemplo](evidencias/swagger-erros-documentados.png)

**2. O mesmo endpoint depois de "Try it out" → "Execute" — chamada real, resposta real, batendo com o que estava documentado:**

![Try it out executado: curl real, request URL real, resposta 403 real do servidor](evidencias/swagger-try-it-out.png)

Spec completa de cada serviço: catálogo em [`/docs`](https://leonardo-oliveira-isw055.lapps.studio/docs) (público); `auth-service` e `log-service` exportados em [`docs/openapi/`](openapi/) (sem porta publicada, não dá pra servir Swagger pra fora — ver [Documentação da API](#documentação-da-api-swaggeropenapi)).

### Atividade 5 — Auditoria: login, favoritar, comentar, ação negada e consulta como admin

Roteiro da demonstração pedida pelo professor: login → favoritar um filme → comentar → tentar uma ação de admin sem ser admin (403) → logout → consultar o log como admin (`GET /admin/logs`) e ver todos os eventos, na ordem certa. As ações de login/favoritar/comentar/logout foram executadas por `curl` contra os containers reais (`docker compose up`) e o MySQL de verdade antes dos prints abaixo — os prints em si (Swagger UI) capturam as duas pontas que precisam de prova visual: a tentativa negada e a consulta do log.

**1. Usuário `nerd` (não-admin) tentando uma ação exclusiva de admin — recusado com 403:**

![Usuário nerd recebe 403 ao tentar GET /admin/comments](evidencias/auditoria-403-negado.png)

**2. Consulta do log como admin — `login`, `favoritar_filme`, `comentar`, `logout` e `acesso_negado:admin` capturados, mais recente primeiro:**

![Consulta de GET /admin/logs como admin, mostrando os eventos na ordem certa](evidencias/auditoria-consulta-admin.png)

**3. Usuário comum tentando consultar o log — recusado com 403 (o catálogo nem chega a repassar pro log-service):**

![Usuário comum recebe 403 ao tentar GET /admin/logs](evidencias/auditoria-403-consulta.png)

### Atividade 4 — RBAC: mesma ação, dois papéis

Mesma chamada (`PATCH /auth/admin/users/{id}/role`, promover um usuário), dois tokens diferentes — o `cinefilo` é recusado, o `admin` executa. Validado por curl direto no `auth-service` local antes do print (respostas reais, não simuladas): `cinefilo` → `403 {"detail":"Acesso restrito a admins"}`, `admin` → `200` com o `role` do usuário-alvo atualizado.

**1. Usuário comum (`cinefilo`) tentando promover alguém — recusado com 403:**

![Usuário comum recebe 403 ao tentar ação de admin](evidencias/rbac-403-comum.png)

**2. Admin de verdade fazendo a mesma chamada — sucesso:**

![Admin executa a promoção com sucesso](evidencias/rbac-200-admin.png)

Evidências pedidas pelo professor pra atividade 3 — fluxo completo de recuperação de senha e confirmação de que o `auth-service` não é acessível de fora.

**1. Pedido de redefinição enviado:**

![Pedido de redefinição enviado](evidencias/pedido-enviado.png)

**2. E-mail recebido no Mailtrap, com o link e o token:**

![E-mail de redefinição recebido no Mailtrap](evidencias/email-recebido.png)

**3. Link usado → senha redefinida com sucesso:**

![Senha redefinida com sucesso](evidencias/redefinicao-sucesso.png)

**4. Tentativa de reusar o mesmo link → recusada:**

![Tentativa de reuso do link recusada](evidencias/link-reutilizado-recusado.png)
