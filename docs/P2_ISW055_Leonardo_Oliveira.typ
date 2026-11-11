// ============================================================
//  P2 — Relatório consolidado: arquitetura e atividades (INDIVIDUAL)
//  ISW055 · Introdução à Computação em Nuvem · Fatec Pompeia · 2026.2
//
//  COMO USAR
//  1. Preencha a seção DADOS DO ALUNO logo abaixo.
//  2. Escreva a seção "Arquitetura do SaaS" seguindo os subtítulos-guia.
//  3. Em cada #atividade(...), preencha "realizada", "situacao" e "url"
//     e escreva o corpo: o que você fez, prints e dificuldades.
//  4. Salve os prints numa pasta "prints/" ao lado deste arquivo e troque
//     `arquivo: none` por `arquivo: "prints/nome-do-print.png"`.
//  5. Compile em https://typst.app (Novo projeto → envie este arquivo e a
//     pasta prints) ou no terminal: typst compile P2_ISW055_template.typ
//  6. Apague os blocos cinza de orientação quando terminar.
//
//  Entrega: 10/11/2026 · PDF nomeado P2_ISW055_Nome_Sobrenome.pdf,
//  em docs/ do repositório do produto, com link no README e uma issue
//  "Entrega — P2" mencionando @siriani
// ============================================================

// ---------- DADOS DO ALUNO (edite aqui) ----------
#let aluno = "Leonardo Ricci Santos Oliveira"
#let turma = "161_SIST. INTELIGENTES_N"
#let produto = "ProvaPronta"
#let repositorio = "https://github.com/leonardoricci-tsi/ProvaPronta"
#let data-relatorio = "10/11/2026"

// ---------- daqui pra baixo, só mexa nas seções e nas fichas ----------
#let disciplina = "Introdução à Computação em Nuvem"
#let codigo = "ISW055"
#let professor = "Prof. Allan Lincoln Rodrigues Siriani"
#let accent = rgb("#b96f1f")

#set document(title: "P2 — " + codigo + " — " + aluno, author: aluno)
#set page(paper: "a4", margin: (top: 2.5cm, bottom: 2.5cm, left: 2.5cm, right: 2cm))
#set text(size: 11pt, lang: "pt", region: "BR")
#set par(justify: true, leading: 0.7em)
#set heading(numbering: "1.1")
#show heading.where(level: 1): it => { v(0.6em); text(size: 16pt, it); v(0.2em) }
#show heading.where(level: 2): it => { v(0.5em); text(size: 13pt, it); v(0.1em) }
#show link: set text(fill: accent)
#show figure.caption: set text(size: 9pt, fill: luma(90))
#set table(stroke: 0.5pt + luma(200), inset: 6pt)
#show table: set text(hyphenate: false)
#show table: set par(justify: false)

// ---------- ajudantes ----------
#let orientacao(body) = block(
  width: 100%, fill: luma(245), inset: 9pt, radius: 4pt,
  stroke: (left: 2pt + luma(180)),
  text(size: 9.5pt, fill: luma(90), body),
)

#let evidencia(legenda, arquivo: none) = figure(
  if arquivo == none {
    rect(width: 100%, height: 5.5cm, radius: 4pt, stroke: (paint: luma(170), dash: "dashed"))[
      #align(center + horizon)[
        #text(fill: luma(130), size: 9.5pt)[
          cole o print ou o diagrama aqui \
          troque `arquivo: none` por `arquivo: "prints/nome.png"`
        ]
      ]
    ]
  } else {
    image(arquivo, width: 100%)
  },
  kind: image,
  supplement: [Figura],
  caption: legenda,
)

#let registro = state("registro", ())

#let registrar(numero, titulo, planejada, realizada, situacao) = registro.update(l => l + ((
  numero: numero, titulo: titulo,
  planejada: planejada, realizada: realizada, situacao: situacao,
),))

#let atividade(
  numero, titulo,
  descricao: "",
  planejada: "",
  realizada: "—",
  situacao: "entregue",   // entregue · entregue com atraso · não entregue
  evidencia: "",
  url: "",
  corpo,
) = {
  registrar(numero, titulo, planejada, realizada, situacao)
  heading(level: 2, [Atividade #numero — #titulo])
  table(
    columns: (3.4cm, 1fr),
    fill: (x, y) => if x == 0 { luma(245) } else { none },
    [*Descrição*], [#descricao],
    [*Data planejada*], [#planejada],
    [*Data realizada*], [#realizada],
    [*Situação*], [#situacao],
    [*Evidência*], [#evidencia],
    [*Link*], [#if url == "" [—] else [#link(url)]],
  )
  corpo
}

// ============================================================
//  CAPA
// ============================================================
#align(center)[
  #v(2.5cm)
  #text(size: 12pt, tracking: 0.12em)[FATEC POMPEIA]
  #v(0.4em)
  #text(size: 10.5pt, fill: luma(110))[#disciplina · #codigo · #turma]
  #v(4cm)
  #text(size: 26pt, weight: "bold")[P2]
  #v(0.3em)
  #text(size: 18pt, weight: "bold")[Relatório consolidado]
  #v(0.2em)
  #text(size: 13pt)[arquitetura e atividades do 2º bimestre]
  #v(0.8em)
  #text(size: 11pt, fill: luma(110))[Avaliação individual · 2026.2]
  #v(3.2cm)
  #text(size: 14pt)[#aluno]
  #v(0.5em)
  #text(size: 11pt)[Produto: *#produto*] \
  #text(size: 9.5pt)[#link(repositorio)]
  #v(1fr)
  #text(size: 10.5pt)[#professor \ Pompeia, #data-relatorio]
]

#set page(
  numbering: "1",
  number-align: right,
  header: context {
    set text(size: 8pt, fill: luma(120))
    [#codigo · P2 — Relatório consolidado #h(1fr) #aluno]
    line(length: 100%, stroke: 0.4pt + luma(200))
  },
)
#counter(page).update(1)

#outline(title: "Sumário", indent: 1.2em, depth: 2)
#pagebreak()

// ============================================================
= Introdução
// ============================================================
A disciplina de Introdução à Computação em Nuvem foi construída em cima de um único projeto que cresceu a cada atividade. No primeiro bimestre ele era um catálogo de filmes do Tom Hanks: uma API em FastAPI que foi ganhando login separado num microsserviço, controle de acesso por papel, auditoria com Redis, upload de arquivos num object storage, CI/CD e observabilidade, tudo rodando numa stack do Portainer na VM da disciplina, com um subdomínio próprio. No segundo bimestre a ideia mudou de escala: em vez de só aprender as peças, transformar o projeto num produto de verdade, com plano pago, documentação, plano de negócio e assinatura recorrente.

O produto que escolhi é o *ProvaPronta*, um SaaS para professores. A dor vem de perto: um professor da rede pública com várias turmas passa horas montando prova no Word, imprimindo, corrigindo à mão e lançando nota em planilha, quase tudo fora do horário pago. No ProvaPronta o professor organiza turmas e alunos, guarda os PDFs do material numa biblioteca, gera questões de múltipla escolha com IA a partir desses PDFs, cria uma versão B embaralhada contra cola e imprime uma folha de respostas por aluno, com QR code, pensada para ser corrigida pela foto do celular. A cobrança é feita pelo Stripe, com um plano Free, o Professor Pro e o plano Escola para a coordenação.

Este relatório tem duas partes. A primeira descreve a arquitetura do sistema que está no ar hoje em #link("https://leonardo-oliveira-isw055.lapps.studio")[leonardo-oliveira-isw055.lapps.studio]: componentes, onde rodam, o caminho de uma requisição, o fluxo da assinatura, o modelo de dados, a segurança, a observabilidade e as camadas de nuvem. A segunda presta contas das atividades 7 a 11, com a data planejada, a data em que cada uma foi entregue e a evidência de cada entrega.

// ============================================================
= Metodologia
// ============================================================
As atividades 7 e 8 foram feitas no repositório público do catálogo de filmes (`api_filme_`), o mesmo do 1º bimestre. Na atividade 9, esse repositório foi copiado com todo o histórico (`git clone --bare` + `git push --mirror`) para um repositório novo, com o nome do produto, onde o SaaS foi desenvolvido nas atividades 10 e 11, na mesma stack do Portainer e no mesmo domínio. A data e a hora de cada entrega foram extraídas do histórico de commits (`git log`), conferidas na página do commit no GitHub e, da atividade 9 em diante, na issue de entrega que menciona o professor. Os prints mostram o README com a menção ao professor, o histórico de commits e o sistema em execução.

O desenvolvimento foi feito localmente no meu Mac, com o Docker Compose subindo a mesma stack de produção (api, auth-service, log-service, Redis e Garage) e um MySQL local; os testes automatizados rodam com pytest num container Python, e o frontend em Angular é compilado para dentro da imagem da api. Usei o Claude Code como assistente de programação ao longo do bimestre, revisando e testando o que era gerado antes de cada commit. Cada entrega seguiu o mesmo caminho: commit no `main`, GitHub Actions rodando os testes, o build das imagens e um smoke test com a stack inteira, publicação das imagens no GHCR e o Portainer puxando a versão nova por GitOps. Quando a entrega mudava o banco, a migration do Alembic era aplicada pelo console do container da api no Portainer. As partes externas (Stripe em modo de teste, domínio de e-mail no Resend, variáveis da stack) foram configuradas nos painéis de cada serviço.

Como o GitHub só mostra a hora exata de um commit ou de uma issue ao passar o mouse sobre a data, a evidência de cada atividade junta dois prints: a página do commit ou da issue de entrega (repositório, hash ou número, título) e o mesmo registro aberto pela API pública do GitHub (`api.github.com`), que mostra a data e a hora exatas. A API usa o horário UTC; no quadro de entregas as horas estão convertidas para o horário de Brasília (UTC−3).

// ============================================================
= Arquitetura do SaaS
// ============================================================
== Visão geral e componentes
#evidencia([Componentes do ProvaPronta: o que é público, o que fica só na rede interna da stack e os serviços externos], arquivo: "prints/p2-componentes.png")

#table(
  columns: (3cm, 1fr, 3.2cm, 2.4cm),
  fill: (x, y) => if y == 0 { luma(235) } else { none },
  table.header([*Componente*], [*Responsabilidade*], [*Tecnologia / imagem*], [*Público?*]),
  [api], [telas (Angular), API do negócio, landing, webhook do Stripe, leitura da folha por foto], [FastAPI · `provapronta`], [sim (domínio, porta 8215)],
  [auth-service], [cadastro, login, JWT, papéis (RBAC), e-mails], [FastAPI · `provapronta-auth`], [não (só rede interna)],
  [log-service], [eventos de negócio e auditoria], [FastAPI · `provapronta-log`], [não],
  [Redis], [stream `audit_log` com os eventos], [`redis:7-alpine`], [não],
  [MySQL (no lugar do MariaDB)], [domínio, usuários, assinaturas], [servidor remoto da disciplina], [não (fora da stack)],
  [Garage (no lugar do MinIO)], [PDFs das apostilas e fotos de perfil, bucket privado], [`provapronta-garage` (S3)], [não; link pré-assinado via api],
  [Stripe (externo)], [checkout, assinaturas, portal, webhooks], [serviço SaaS, modo de teste], [webhook → api],
  [Groq e Resend (externos)], [LLM para gerar questões; SMTP dos e-mails], [serviços SaaS], [não],
)

== Onde roda
O sistema roda na mesma stack do Portainer usada desde o 1º bimestre, `api-tom-hanks-leonardo`, na VM da disciplina e no mesmo subdomínio. Na atividade 10 a stack passou a puxar o código do repositório novo, `leonardoricci-tsi/ProvaPronta`; como o Portainer CE não deixa trocar a URL do Git de uma stack, ela foi removida e recriada com o mesmo nome, as mesmas variáveis e os mesmos volumes. O arquivo usado é o `docker-compose.portainer.yml`, e o Portainer verifica o repositório a cada 5 minutos (GitOps).

São cinco containers: `api` (imagem `ghcr.io/leonardoricci-tsi/provapronta`), `auth-service` (`provapronta-auth`), `log-service` (`provapronta-log`), `redis` (`redis:7-alpine`) e `garage` (`provapronta-garage`). Todos têm health check. Só a api publica porta (8215, para onde o proxy HTTPS do domínio aponta); os outros quatro existem apenas na rede interna `catalog-net`. O compose não define limite de memória por container: os containers usam a memória disponível da VM. Os dados ficam em volumes nomeados (`redis-data`, `garage-meta`, `garage-data`) e no MySQL remoto da disciplina, que fica fora da stack.

As variáveis de ambiente da stack são: `DATABASE_URL`, `JWT_SECRET`, `JWT_EXPIRE_MINUTES`, `AUTH_SERVICE_URL`, `LOG_SERVICE_URL`, `REDIS_URL`, `CATALOG_PUBLIC_URL`, `S3_ENDPOINT_URL`, `S3_PUBLIC_URL`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET`, `GARAGE_RPC_SECRET`, `GARAGE_DEFAULT_ACCESS_KEY`, `GARAGE_DEFAULT_SECRET_KEY`, `GARAGE_DEFAULT_BUCKET`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_FROM_NAME`, `STRIPE_SECRET_KEY`, `STRIPE_PRICE_PRO`, `STRIPE_PRICE_ESCOLA`, `STRIPE_WEBHOOK_SECRET`, `LLM_API_KEY`, `LLM_BASE_URL` e `LLM_MODEL`. Os valores ficam só no Portainer. A URL pública é #link("https://leonardo-oliveira-isw055.lapps.studio")[https://leonardo-oliveira-isw055.lapps.studio], com a documentação da API em `/docs`.

== Fluxo de uma requisição
A ação mais comum do produto é o professor criar uma prova. O caminho completo é:

+ O navegador, já logado, envia `POST /provas` para o domínio, com o JSON da prova e o cabeçalho `Authorization: Bearer <JWT>`. O token foi emitido pelo auth-service no login e fica guardado no navegador.
+ O proxy HTTPS da disciplina recebe a requisição no subdomínio e repassa para a porta 8215 da api.
+ A api valida o JWT localmente, com o mesmo `JWT_SECRET` do auth-service, e lê dele o id do usuário e o papel (`professor`, `professor_pro`, `coordenador` ou `admin`). Token ausente ou inválido responde `401`. O auth-service não precisa ser chamado a cada requisição; ele é consultado para login, cadastro, troca de papel e dados de usuário.
+ A api confere no MySQL se a turma informada é do próprio usuário, com o filtro `usuario_id` na consulta. Se for de outra pessoa, responde `404`, como se não existisse.
+ Se o papel é Free, a api conta as provas criadas no mês. Na terceira responde `403` com a mensagem do limite e registra `acesso_negado:limite_free:provas`.
+ A api grava a prova e as questões no MySQL numa transação.
+ A api manda o evento `prova_criada:{id}` para o log-service (`POST /logs`), sem esperar resposta: se o log cair, a prova é criada do mesmo jeito. O log-service grava o evento no stream `audit_log` do Redis.
+ O navegador recebe `201 Created` com a prova em JSON.

#evidencia([Fluxo de uma requisição: o professor cria uma prova (POST /provas)], arquivo: "prints/p2-requisicao.png")

== Fluxo de assinatura
Os planos são o Free (padrão de todo cadastro, sem passar pelo Stripe), o Professor Pro (R\$ 29,90 por mês) e o Escola (R\$ 199,90 por mês), os dois pagos criados no Stripe como produtos com preço recorrente mensal. Cada plano é um papel do RBAC: assinar o Pro troca o papel de `professor` para `professor_pro`.

Quando o professor clica em "Assinar", a api cria, uma única vez, o customer do Stripe dele e guarda o ID na tabela `assinaturas`; depois abre uma Checkout Session com `mode=subscription` e devolve a URL. O cartão é digitado na página do Stripe e nunca passa pelo servidor. A volta do navegador (`?checkout=sucesso`) não ativa nada: quem muda o plano é o webhook, e a tela fica consultando `GET /premium/status` até ele chegar.

O webhook chega em `POST /premium/webhook`. A primeira coisa é validar o cabeçalho `Stripe-Signature`, um HMAC do corpo bruto com o segredo do endpoint e um timestamp: sem assinatura válida a resposta é `400` e nada é gravado. Depois a api trata quatro eventos:

- `checkout.session.completed`: troca o papel no auth-service e grava na tabela `assinaturas` o customer, a assinatura, o status `active` e o valor mensal;
- `customer.subscription.updated`: atualiza plano, status e valor. O plano é lido pelo preço, então uma troca de Pro para Escola feita no portal também vale. Status fora de `active` e `trialing` (por exemplo `past_due`) volta a conta para o Free;
- `customer.subscription.deleted`: a assinatura acabou, a conta volta para o Free;
- `invoice.payment_failed`: marca `past_due`, volta para o Free na hora, manda um e-mail de aviso e mostra um alerta em todas as telas. Se o pagamento passar depois, o `updated` com `active` devolve o plano.

Se o mesmo evento chegar duas vezes, a segunda entrega é ignorada: o ID de cada evento processado fica na tabela `eventos_stripe`. Se um evento falhar no meio (por exemplo, o auth-service fora do ar), a api responde `502`, o evento não é marcado e o Stripe reenvia. Uma assinatura cancelada também não é reativada por um `updated` que chegue atrasado. O cancelamento é feito pelo botão "Gerenciar assinatura", que abre o portal do cliente do Stripe, configurado para cancelamento imediato. Com o plano novo no papel, a próxima requisição da api já não aplica o limite do Free.

#evidencia([Fluxo de assinatura: checkout → webhook validado → plano no banco → cancelamento pelo portal], arquivo: "prints/p2-assinatura.png")

== Modelo de dados do domínio
O domínio tem quatro tabelas principais com chave estrangeira: `turmas`, `alunos` (FK `turma_id`, apagada junto com a turma), `provas` (FK `turma_id` com `RESTRICT`: não dá para apagar uma turma que tem prova) e `questoes` (FK `prova_id`, apagada junto com a prova). A biblioteca de materiais tem `pastas` e `materiais` (FK `pasta_id`). O PDF e as fotos ficam no Garage; no banco fica só a chave do objeto.

A tabela `usuarios` pertence ao auth-service. As tabelas da api guardam o `usuario_id` sem chave estrangeira para ela, porque cada serviço é dono das próprias tabelas; a ligação é lógica e é garantida pelo JWT. É o `usuario_id` que liga o usuário ao plano: o papel (`role`) fica em `usuarios`, e a tabela `assinaturas` (chave `usuario_id`) guarda `stripe_customer_id`, `stripe_subscription_id`, `plano`, `status` e `valor_mensal_centavos`. A tabela `eventos_stripe` guarda os IDs dos eventos já processados. O esquema é versionado por migrations do Alembic (`alembic/versions/`) e pelo DDL em `db/`.

#evidencia([Modelo de dados: tabelas do domínio, chaves estrangeiras e a ligação usuário → assinatura do Stripe], arquivo: "prints/p2-dados.png")

== Segurança
#table(
  columns: (1fr, 2.9cm, 2.6cm, 2.6cm),
  align: (left, center, center, center),
  fill: (x, y) => if y == 0 { luma(235) } else { none },
  table.header([*Ação*], [*Free (`professor`)*], [*Pro (`professor_pro`)*], [*Escola (`coordenador`)*]),
  [criar turmas, provas, PDFs], [até 1 turma, 2 provas/mês, 3 PDFs], [ilimitado], [ilimitado],
  [versão B embaralhada, gerar questões com IA], [não (403)], [sim], [sim],
  [aprovar prova, relatório da coordenação], [não (403)], [não (403)], [sim],
  [ver turma ou prova de outro usuário], [não (404)], [não (404)], [não (404)],
  [painel admin, trocar papéis, ler o log], [não (403)], [não (403)], [não (403) — só `admin`],
)

Os papéis formam uma escada: `professor` (Free) < `professor_pro` < `coordenador` (Escola) < `admin`, e cada um inclui o anterior. O papel vem só do JWT e quem barra é a API, com uma dependência que exige o papel mínimo; as telas apenas escondem botões. Toda ação acima do papel responde `403` também quando a API é chamada direto, e registra um evento `acesso_negado:*`. O admin tem ainda o painel com usuários, troca de papéis, eventos de auditoria e a visão geral do negócio.

O isolamento por usuário fica nas consultas: toda leitura de turma, prova, pasta ou PDF filtra pelo `usuario_id` do token, por uma função única (`get_owned_or_404`). O recurso de outra pessoa responde `404`, e não `403`, para não revelar que o ID existe. Nem o coordenador aprova prova de outro professor. Os arquivos no Garage só abrem por link pré-assinado, que expira e só é gerado para o dono.

Os segredos (`JWT_SECRET`, senha do banco, chaves do Stripe, do Garage, do SMTP e da IA) ficam só nas variáveis da stack no Portainer. O repositório tem apenas o `.env.example`, com os nomes e sem valores, e o `.env` está no `.gitignore`. O CI usa um `.env` descartável com valores aleatórios a cada execução.

== Observabilidade, CI/CD e documentação da API
Fiz as três extras no 1º bimestre e elas continuam no produto:

- *Documentação da API:* o Swagger fica em `/docs`, com os erros de cada rota (401, 403, 404, 409, 422, 503) documentados com exemplo.
- *CI/CD:* o GitHub Actions roda os testes da api (199 hoje) e do log-service, faz o build das quatro imagens, sobe a stack inteira num smoke test que repete o fluxo de turma, prova, PDF, 404 e 403, publica as imagens no GHCR com a tag do commit e faz um commit automático (`deploy: sha-…`) apontando o compose de produção para essa tag. O Portainer puxa por GitOps; não há deploy manual.
- *Observabilidade:* todos os containers têm health check, e `/health` da api mostra o estado do MySQL, do auth-service, do log-service e do Garage. Cada serviço expõe `/metrics` (Prometheus) numa porta interna, a 9100, fora do domínio público. O Prometheus e o painel do Grafana sobem só no ambiente local (`docker-compose.yml`); em produção ficam os health checks e as métricas internas.

== Camadas IaaS, PaaS e SaaS do projeto
#table(
  columns: (2cm, 1fr, 3.6cm),
  fill: (x, y) => if y == 0 { luma(235) } else { none },
  table.header([*Camada*], [*O que é no seu projeto*], [*Quem gerencia*]),
  [IaaS], [a VM da disciplina, a rede e o disco onde a stack roda], [professor / Fatec],
  [PaaS], [Docker + Portainer, MySQL remoto, proxy HTTPS do domínio, GitHub Actions e GHCR; Redis e Garage rodam como containers da minha stack], [professor (VM, Portainer, MySQL, domínio); GitHub (CI e registro); eu (containers)],
  [SaaS], [o ProvaPronta para os professores; e os SaaS que eu uso: Stripe, Resend, Groq, GitHub], [eu (o produto); os fornecedores (os outros)],
)

// ============================================================
= Quadro de entregas
// ============================================================
#context {
  let l = registro.final().sorted(key: a => a.numero)
  table(
    columns: (auto, 1fr, 2.3cm, 3.6cm, 2.4cm),
    align: (center, left, center, center, center),
    fill: (x, y) => if y == 0 { luma(235) } else { none },
    table.header([*Nº*], [*Atividade*], [*Data \ planejada*], [*Data \ realizada*], [*Situação*]),
    ..l.map(a => ([#a.numero], [#a.titulo], [#a.planejada], [#a.realizada], [#a.situacao])).flatten(),
  )
}

// ============================================================
= Atividades realizadas
// ============================================================
#atividade(
  7, "Plano Premium — cobrança de verdade com Stripe",
  descricao: "Plano pago em modo de teste: Checkout Session do Stripe e webhook marcando o usuário como premium.",
  planejada: "09/10/2026",
  realizada: "09/10/2026 16:33",
  situacao: "entregue",
  evidencia: "GitHub — commit b0b0ace (repositório antigo `api_filme_`) e issue #10 do repositório antigo + prints do checkout concluído e do usuário premium",
  url: "https://github.com/leonardoricci-tsi/api_filme_/commit/b0b0ace022e08357cc02922b308040bafe9d43ce",
)[
  *O que foi feito.* O catálogo de filmes ganhou planos pagos de verdade, no modo de teste do Stripe. Criei dois planos, Nerd e Stalker, cada um ligado a um papel do RBAC, e uma Checkout Session hospedada pelo Stripe, de modo que o número do cartão nunca chega ao servidor. O webhook `checkout.session.completed`, com a assinatura `Stripe-Signature` validada, é o único caminho que ativa o plano: ele pede ao auth-service a troca do papel e grava a assinatura no banco. O usuário gratuito ficou limitado a 5 favoritos, e o perfil passou a mostrar o selo do plano.

  #evidencia([Atividade 7 — evidência da entrega: a página no GitHub e o mesmo registro na API do GitHub, com data e hora (UTC)], arquivo: "prints/p2-a7-evidencia.png")
  #evidencia([Atividade 7 — resultado: pagamento confirmado pelo webhook e usuário com plano pago], arquivo: "evidencias/planos-4-pagamento-confirmado-nerd.jpg")

  *Mais prints do resultado:*

  #grid(
    columns: 2, gutter: 10pt,
    evidencia([Atividade 7 — Usuário gratuito barrado no limite de favoritos (403)], arquivo: "evidencias/planos-1-gratuito-403-favoritar.jpg"),
    evidencia([Atividade 7 — Checkout do Stripe em modo de teste], arquivo: "evidencias/planos-3-checkout-stripe-nerd.jpg"),
    evidencia([Atividade 7 — Com o plano pago, o mesmo favorito é aceito (201)], arquivo: "evidencias/planos-5-nerd-201-favoritar.jpg"),
    evidencia([Atividade 7 — Assinatura gravada no banco e papel trocado pelo webhook], arquivo: "evidencias/planos-8-mysql-assinatura-e-papel.png"),
  )

  *Dificuldades e como foram resolvidas.* A parte mais delicada foi o webhook: a assinatura é calculada sobre o corpo bruto da requisição, então a rota tem que ler os bytes exatos que o Stripe mandou, sem o FastAPI interpretar o JSON antes. Também foi preciso aceitar que o navegador volta do checkout antes de o webhook chegar; a página de planos passou a consultar o status até o plano aparecer e a renovar o token para o papel novo valer.
]

#atividade(
  8, "SaaS, PaaS, IaaS — e a documentação que o projeto nunca teve",
  descricao: "Camadas de nuvem do próprio projeto e documentação reversa: especificação, arquitetura, regras de negócio e modelo de dados.",
  planejada: "16/10/2026",
  realizada: "23/10/2026 20:03",
  situacao: "entregue com atraso",
  evidencia: "GitHub — commit f9c19da (repositório antigo) + DOCUMENTACAO.md linkado no README",
  url: "https://github.com/leonardoricci-tsi/api_filme_/commit/f9c19da6d60c294f987b7de491b66b6ab7fb9bba",
)[
  *O que foi feito.* Documentei o sistema como se ele tivesse sido herdado de outra pessoa, sem escrever código novo. O `DOCUMENTACAO.md` traz a especificação, a arquitetura, as regras de negócio extraídas do código (cada uma com o arquivo de onde saiu), o modelo de dados e uma seção de achados da leitura, onde o código fazia algo diferente do que o README dizia. No README ficou a classificação de cada peça do projeto nas camadas SaaS, PaaS e IaaS, com o link para a documentação.

  #evidencia([Atividade 8 — evidência da entrega: a página no GitHub e o mesmo registro na API do GitHub, com data e hora (UTC)], arquivo: "prints/p2-a8-evidencia.png")
  #evidencia([Atividade 8 — resultado: DOCUMENTACAO.md no repositório, linkada pelo README], arquivo: "prints/p2-a8-documentacao.png")

  *Mais prints do resultado:*

  #grid(
    columns: 1, gutter: 10pt,
    evidencia([Atividade 8 — README do repositório antigo com a classificação nas camadas e o link para a DOCUMENTACAO.md], arquivo: "prints/p2-a8-readme-antigo.png"),
  )

  *Dificuldades e como foram resolvidas.* *Atraso:* a atividade foi entregue em 23/10, uma semana depois do prazo de 16/10. Atrasei a entrega porque achei que ela já tinha sido feita junto com o relatório da P1; depois que o professor avisou em sala, fiz a atividade, já com atraso. A maior dificuldade foi a própria leitura reversa: separar o que o código realmente faz do que a documentação antiga prometia, e classificar nas camadas de nuvem peças que dependem de quem gerencia cada uma (o mesmo container é PaaS para mim porque a VM e o Docker já existiam).
]

#atividade(
  9, "Fork e plano de negócio",
  descricao: "Repositório novo com o histórico do anterior, README do produto (dor, persona, Lean Canvas, modelo de receita, mapa de reaproveitamento) e backlog em issues.",
  planejada: "23/10/2026",
  realizada: "23/10/2026 22:39",
  situacao: "entregue",
  evidencia: "GitHub — issue #15 “Entrega — Fork e plano de negócio” (@siriani) + repositório novo + README do produto + histórico e issues",
  url: "https://github.com/leonardoricci-tsi/ProvaPronta/issues/15",
)[
  *O que foi feito.* Escolhi o domínio do produto e criei o repositório novo, `ProvaPronta`, copiando o antigo com todo o histórico (`git clone --bare` e `git push --mirror`), para que os commits do 1º bimestre e das atividades 7 e 8 continuassem verificáveis. O README do produto ganhou a dor, a persona (a professora Marta, com oito turmas), os concorrentes, a proposta de valor, o modelo de receita com Free, Pro e Escola, o Lean Canvas e o mapa do que seria reaproveitado do catálogo. O backlog virou 14 issues, separadas pelas atividades seguintes, e o repositório antigo ganhou no topo um aviso apontando para o novo.

  #evidencia([Atividade 9 — evidência da entrega: a página no GitHub e o mesmo registro na API do GitHub, com data e hora (UTC)], arquivo: "prints/p2-a9-evidencia.png")
  #evidencia([Atividade 9 — resultado: README do produto no repositório novo], arquivo: "prints/p2-a9-readme.png")

  *Mais prints do resultado:*

  #grid(
    columns: 2, gutter: 10pt,
    evidencia([Atividade 9 — Histórico copiado: os commits das atividades 7 e 8 no repositório novo], arquivo: "prints/p2-a9-historico.png"),
    evidencia([Atividade 9 — Backlog do produto em issues, com as entregas], arquivo: "prints/p2-a9-issues.png"),
  )

  *Dificuldades e como foram resolvidas.* A dificuldade foi escolher um produto que reaproveitasse a infraestrutura que eu já tinha (login separado, papéis, auditoria, upload e Stripe) e que tivesse uma dor real e um diferencial claro. Também foi preciso fazer a cópia do repositório de um jeito que preservasse o histórico, em vez de começar do zero.
]

#atividade(
  10, "Seu negócio no ar — o domínio no lugar dos filmes",
  descricao: "Stack apontando para o repositório novo, tabelas e API do domínio, papéis do negócio, isolamento por usuário, eventos no log, upload e landing page.",
  planejada: "06/11/2026",
  realizada: "03/11/2026 16:15",
  situacao: "entregue",
  evidencia: "GitHub — issue #16 “Entrega — Seu negócio no ar” (@siriani) + commit + URL no ar + prints da landing, do 403 e dos eventos",
  url: "https://github.com/leonardoricci-tsi/ProvaPronta/issues/16",
)[
  *O que foi feito.* Troquei os filmes pelo domínio do ProvaPronta no mesmo endereço. A stack do Portainer passou a puxar do repositório novo, com as imagens renomeadas para `provapronta-*`. Criei as tabelas do domínio (turmas, alunos, provas e questões) com chaves estrangeiras, a API e as telas de cada uma, os papéis do negócio (Free, Pro, Escola e admin) com ações exclusivas para cada um, o isolamento por usuário com resposta 404, os eventos de negócio no log, o upload do PDF da apostila no Garage e a landing page com os planos. Depois da entrega o produto continuou crescendo: biblioteca de materiais em pastas, geração de questões com IA, folhas de resposta com QR code e e-mails pelo Resend com domínio próprio.

  #evidencia([Atividade 10 — evidência da entrega: a página no GitHub e o mesmo registro na API do GitHub, com data e hora (UTC)], arquivo: "prints/p2-a10-evidencia.png")
  #evidencia([Atividade 10 — resultado: landing do ProvaPronta no ar], arquivo: "prints/a10-01-landing.jpg")

  *Mais prints do resultado:*

  #grid(
    columns: 2, gutter: 10pt,
    evidencia([Atividade 10 — Listagem de provas da professora (plano Pro)], arquivo: "prints/a10-02-listagem-provas.jpg"),
    evidencia([Atividade 10 — 403: o Pro tenta aprovar uma prova, ação do plano Escola], arquivo: "prints/a10-03-403-aprovar-pro.jpg"),
    evidencia([Atividade 10 — 404: prova de outro usuário], arquivo: "prints/a10-04-404-prova-de-outro.jpg"),
    evidencia([Atividade 10 — PDF da apostila anexado à prova], arquivo: "prints/a10-05-pdf-anexado.jpg"),
    evidencia([Atividade 10 — Relatório da coordenação (plano Escola)], arquivo: "prints/a10-07-coordenacao-relatorio.jpg"),
    evidencia([Atividade 10 — Eventos de negócio no log-service], arquivo: "prints/a10-09-eventos-log.jpg"),
    evidencia([Atividade 10 — Os containers da stack no Portainer, saudáveis], arquivo: "prints/a10-10-portainer-containers.png"),
  )

  *Dificuldades e como foram resolvidas.* Para mim foi a atividade mais difícil, porque foi preciso mudar toda a infraestrutura para o projeto novo sem perder o que já estava no ar. O Portainer CE não deixa trocar o repositório de uma stack Git, então ela teve que ser removida e recriada com o mesmo nome, as mesmas variáveis e os mesmos volumes. Também foi preciso criar um bucket novo no Garage, refazer as integrações (Stripe, e-mail, chaves da IA) nas variáveis da stack, aplicar as migrations do banco pelo console do container e descobrir que o Cloudflare na frente do domínio trocava as respostas 502 da api pela página de erro dele, o que escondia a mensagem real.
]

#atividade(
  11, "SaaS completo — planos, limites e assinatura com Stripe",
  descricao: "Planos recorrentes, checkout de assinatura, webhooks atualizando o plano, portal do cliente, limites por plano na API e painel admin.",
  planejada: "13/11/2026",
  realizada: "10/11/2026 20:19",
  situacao: "entregue",
  evidencia: "GitHub — issue #17 “Entrega — SaaS completo” (@siriani) + commits 3fa8ebf e 90faeb5 + prints da assinatura com o cartão 4242, do webhook e do limite",
  url: "https://github.com/leonardoricci-tsi/ProvaPronta/issues/17",
)[
  *O que foi feito.* O pagamento virou assinatura recorrente. O checkout passou a criar e guardar o customer do Stripe do usuário, os webhooks passaram a tratar `customer.subscription.updated` e `invoice.payment_failed` além dos dois que já existiam, e cada evento processado é registrado para não ter efeito duas vezes. Entraram o portal do cliente ("Gerenciar assinatura"), com troca de plano e cancelamento imediato, o aviso de pagamento recusado por e-mail e na tela, e a visão geral do painel admin, com usuários por plano, assinaturas ativas, inadimplentes, MRR de teste e últimos eventos. Os limites do Free continuaram barrados na API.

  #evidencia([Atividade 11 — evidência da entrega: a página no GitHub e o mesmo registro na API do GitHub, com data e hora (UTC)], arquivo: "prints/p2-a11-evidencia.png")
  #evidencia([Atividade 11 — resultado: assinatura do Pro confirmada pelo webhook], arquivo: "prints/a11-04-pagamento-confirmado.png")

  *Mais prints do resultado:*

  #grid(
    columns: 2, gutter: 10pt,
    evidencia([Atividade 11 — Limite do Free bloqueando a segunda turma], arquivo: "prints/a11-02-limite-free-tela.png"),
    evidencia([Atividade 11 — Assinatura do Pro com o cartão de teste 4242], arquivo: "prints/a11-03-checkout-4242.png"),
    evidencia([Atividade 11 — Assinatura ativa no painel do Stripe (modo de teste)], arquivo: "prints/a11-06-stripe-assinatura.png"),
    evidencia([Atividade 11 — Webhooks entregues no endpoint /premium/webhook], arquivo: "prints/a11-07-webhook-recebido.png"),
    evidencia([Atividade 11 — Portal do cliente do Stripe], arquivo: "prints/a11-08-portal.png"),
    evidencia([Atividade 11 — Depois do cancelamento, a conta volta ao Free], arquivo: "prints/a11-09-cancelado-free.png"),
    evidencia([Atividade 11 — Painel admin: usuários por plano, assinaturas e MRR de teste], arquivo: "prints/a11-11-admin-visao-geral.png"),
  )

  *Dificuldades e como foram resolvidas.* O deploy travou porque o disco do servidor da disciplina encheu (`no space left on device` ao clonar o repositório); com a orientação do professor, removi as imagens antigas da minha stack e o deploy voltou. No teste real, um evento `customer.subscription.updated` voltou com erro 500 na primeira tentativa e o Stripe reenviou sozinho com sucesso; ao investigar, vi que os eventos do portal podem chegar fora de ordem e corrigi para que uma atualização atrasada não reative uma assinatura cancelada. Também foi preciso configurar o portal do cliente no Stripe, que sem os produtos cadastrados não oferece a troca de plano.
]


// ============================================================
= Considerações finais
// ============================================================
O bimestre mudou o jeito como eu olho para o projeto. No primeiro, cada atividade era uma peça isolada; no segundo, as mesmas peças tiveram que funcionar juntas para sustentar um produto que cobra, limita e audita. Aprendi que a parte mais trabalhosa de um SaaS não é a tela, e sim o que fica em volta dela: mudar toda a infraestrutura para o projeto novo sem derrubar o que estava no ar, integrar Stripe, e-mail e IA pelas variáveis do Portainer, aplicar migrations em produção e lidar com problemas que só aparecem no servidor real, como o Cloudflare escondendo erros, o disco cheio e eventos do Stripe chegando fora de ordem. Também ficou claro o valor do que foi construído no 1º bimestre: CI/CD, testes e logs foram o que me deixou mudar tanta coisa com segurança.

Para o ProvaPronta ser um produto de verdade ainda falta o principal diferencial: a correção por foto completa, com a tela de revisão e as notas da turma (a leitura da folha já existe na API). Também faltam a importação de alunos por planilha, o banco de questões reaproveitável, o cumprimento da LGPD (termos de uso, política de privacidade e retenção das fotos), sair do modo de teste do Stripe e rodar numa infraestrutura própria, com limites de memória, backup e monitoramento em produção.

// ============================================================
= Declaração de autoria
// ============================================================
Declaro que este relatório foi elaborado por mim, individualmente, e que as evidências apresentadas correspondem a entregas de minha autoria, verificáveis nos links informados.

#v(1.5cm)
#grid(
  columns: (1fr, 1fr), gutter: 2cm,
  align(center)[#line(length: 100%, stroke: 0.5pt) \ #aluno],
  align(center)[#line(length: 100%, stroke: 0.5pt) \ Pompeia, #data-relatorio],
)
