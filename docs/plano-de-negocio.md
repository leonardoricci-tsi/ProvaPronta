# ProvaPronta — plano de negócio

> Atividade 9 (ISW055), proposta pelo professor [@siriani](https://github.com/siriani). Escrito antes do código; o que já foi construído está no [README](../README.md). Os limites dos planos abaixo são a visão do produto: o MVP no ar aplica 1 turma e 2 provas por mês no Free, e a versão B no Pro.

**Do PDF do seu material à nota no boletim: o ProvaPronta monta a prova, imprime uma folha com QR code por aluno e corrige pela foto do celular — para professores da educação básica que corrigem centenas de provas por bimestre.**

---

## 1. A dor

**Quem sofre:** professor do ensino fundamental II e médio, principalmente da rede pública, com muitas turmas e pouco tempo fora da sala.

**Quando:** no fim de cada bimestre. São duas tarefas que caem no fim de semana:

1. **Montar a prova.** O professor copia trechos do livro ou da apostila em PDF para o Word, inventa alternativas erradas que façam sentido, monta uma versão B contra cola e digita o gabarito. Para não repetir a prova do ano anterior (que já circula entre os alunos), começa quase do zero.
2. **Corrigir a prova.** Com 8 turmas de 35 alunos, são **280 provas por rodada**. Mesmo com a múltipla escolha, ele confere bolinha por bolinha com o gabarito na mão, soma, e depois digita nota por nota numa planilha ou no diário da escola.

**Quanto custa hoje** (estimativa para a persona abaixo, por bimestre):

| Tarefa | Conta | Tempo |
|---|---|---|
| Montar 2 provas (A/B) por série + recuperação | 3 séries × ~3 h | ~9 h |
| Corrigir múltipla escolha | 280 provas × ~2 min | ~9 h |
| Corrigir dissertativas | 280 provas × ~3 min | ~14 h |
| Lançar notas | 280 notas, digitadas | ~2 h |
| **Total** | | **~34 h por bimestre**, quase tudo fora do horário pago |

Além do tempo: **erro de soma e de digitação** (que vira reclamação de pai e revisão de nota), **prova repetida** que vaza, e nenhum dado de "em qual assunto a turma foi mal" para planejar a recuperação.

**Como resolve hoje:** Word + livro em PDF + caneta vermelha + planilha. Quem é mais digital usa o ChatGPT para sugerir questões e copia o resultado para o Word, mas a correção continua na mão.

## 2. Persona

> **Marta Ribeiro, 41 anos, professora de Biologia na rede estadual de São Paulo.**
>
> Dá 32 aulas por semana em **duas escolas**, para 8 turmas do 1º ao 3º ano do ensino médio (~280 alunos). Sai de casa às 6h30, almoça no carro entre uma escola e outra e chega em casa às 19h. Prepara aula e corrige prova à noite e no domingo.
>
> **O que ela tenta fazer:** aplicar uma prova justa por bimestre, com versões diferentes para fileiras vizinhas, devolver corrigida em uma semana e lançar as notas antes do conselho de classe.
>
> **O que atrapalha:**
> - Cada prova nova leva uma noite inteira de Word, e o livro didático está em PDF que ela não consegue copiar direito.
> - A pilha de 280 provas ocupa dois domingos. Ela já errou soma e teve que refazer nota na frente do aluno.
> - Os alunos não têm celular ou computador para fazer prova on-line na escola, então Google Forms não resolve: a prova **tem que ser em papel**.
> - Ela usa o celular para tudo, mas não tem tempo de aprender ferramenta complicada.
>
> **Frase dela:** *"Eu não me importo de montar a prova. O que me mata é corrigir."*

## 3. Concorrentes e alternativas

| Alternativa | O que faz bem | O que faz mal para a Marta |
|---|---|---|
| **O jeito de sempre** (Word + caneta + planilha) | Grátis, ela já sabe usar | Leva ~34 h por bimestre; erro de soma e digitação; nenhum dado sobre o desempenho da turma |
| **ChatGPT / Gemini** | Sugere questões a partir de um texto | Pode inventar alternativa ou fato (sem mostrar de onde tirou); não monta versões A/B nem layout para imprimir; **não corrige nada**; não guarda banco de questões por turma |
| **ZipGrade** e apps de leitura de gabarito | Corrige múltipla escolha pela câmera | Só lê gabarito: não gera a prova a partir do material dela, não monta versões A/B com o conteúdo, não corrige dissertativa; a identificação do aluno depende de ele preencher o próprio número na folha |
| **Plickers** | Resposta rápida com cartões e câmera | Serve para enquete em sala, não para prova; só múltipla escolha com até 4 opções; não gera prova escrita |
| **Google Forms (quiz)** | Nota automática | Exige celular ou computador por aluno, que a escola pública não tem; prova on-line facilita cola |
| **Bancos de questões prontos** (sites, material da editora) | Muitas questões já revisadas | Não usam o material que **ela** deu em sala; questões conhecidas pelos alunos; não corrigem |

## 4. Proposta de valor

**O ProvaPronta é o único que faz a prova a partir do material que você deu em sala e a corrige pela foto do celular, já sabendo de quem é cada folha — a professora gasta o domingo com a família, não com a pilha de provas.**

## 5. Modelo de receita com Stripe

Assinatura mensal, cobrada pelo Stripe (a mesma integração da atividade 7: checkout hospedado + webhook assinado).

| Plano | Preço | Para quem | Limites |
|---|---|---|---|
| **Free** | **R$ 0** | Professor experimentando | 1 turma (até 40 alunos) · 2 provas por mês · só **múltipla escolha** · correção por foto incluída · 3 PDFs de material |
| **Pro** | **R$ 29,90/mês** | Professor com várias turmas | Turmas e provas ilimitadas · versões A/B embaralhadas · banco de questões reaproveitável · **geração de questões a partir do PDF** · **dissertativa com nota recomendada** (até 600 correções com IA por mês) · exportar notas em planilha |
| **Escola** | **R$ 199,90/mês** | Coordenação pedagógica | Tudo do Pro para até 15 professores · coordenador revisa e aprova a prova antes de imprimir · relatório por turma e por assunto · histórico auditado de alteração de nota |

**Por que o Free limita isso:** a correção de múltipla escolha por foto é visão computacional clássica e custa quase nada para rodar — por isso entra no Free e é ela que faz a professora experimentar. O que custa dinheiro por uso é a **IA** (gerar questões e ler resposta escrita à mão) e o volume de turmas: isso é Pro.

**Por que a Marta pagaria o Pro:** R$ 29,90 é menos de R$ 1 por dia. Se o ProvaPronta devolver **um** dos dois domingos de correção por bimestre, ela recupera umas 15 horas — e com 8 turmas o Free (1 turma) não dá conta. A conversão vem naturalmente na primeira semana de provas.

**Por que uma escola pagaria o Escola:** o coordenador passa a ver todas as provas antes da impressão, sabe em qual assunto cada turma foi mal (para planejar a recuperação) e tem o registro de **quem alterou qual nota, de quanto para quanto e quando** — a resposta para "por que a nota do meu filho mudou?".

## 6. Métricas de sucesso

| Métrica | O que mede | Meta nos 3 primeiros meses |
|---|---|---|
| **Cadastros** | Professores que criaram conta | 150 |
| **Ativação** | % dos cadastrados que corrigiram a 1ª prova por foto em até 7 dias (o "momento aha") | 40% |
| **Assinantes Pro / Escola** | Pagantes ativos | 15 Pro + 1 Escola |
| **MRR** (receita recorrente mensal) | Soma das assinaturas ativas | 15 × R$ 29,90 + R$ 199,90 = **R$ 648,40** |
| **Conversão Free → Pro** | % dos ativos que assinam | 10% |
| **Retenção / churn** | % de assinantes que continuam no mês seguinte | ≥ 85% (o uso é sazonal: pico no fim do bimestre — quem cancela entre bimestres conta como churn) |
| **Provas corrigidas por mês** | Uso real do produto | 2.000 folhas |
| **Tempo médio de correção por folha** | Prova de que a dor foi resolvida | < 10 s (contra ~2 min na mão) |

Todas saem de dados que a arquitetura já registra: cadastros e papéis no `auth-service`, assinaturas na tabela `assinaturas` (webhook do Stripe), eventos de uso no log de auditoria (`prova_corrigida`, `nota_alterada`) e latência no Prometheus.

## 7. Lean Canvas

| Bloco | ProvaPronta |
|---|---|
| **Problema** | 1. Corrigir centenas de provas em papel leva dois fins de semana por bimestre, com erro de soma e de digitação. 2. Montar prova nova a partir do próprio material (PDF) é lento, e a prova antiga vaza. 3. O professor não sabe em qual assunto a turma foi mal. *Hoje:* Word, caneta vermelha, planilha e ChatGPT copiado para o Word. |
| **Segmentos de clientes** | Professores do fundamental II e médio com muitas turmas e prova em papel. **Primeiros a adotar:** professores da rede estadual de SP que já usam o celular em sala e dão aula em mais de uma escola; coordenadores de escolas particulares pequenas. |
| **Proposta única de valor** | A prova sai do seu material e se corrige pela foto do celular, sabendo de quem é cada folha. |
| **Solução** | 1. **Correção por foto:** folha de resposta com QR code por aluno e marcas de alinhamento; a foto vira nota recomendada. 2. **Geração de prova a partir do PDF:** questões com o trecho de origem, versões A/B e gabarito. 3. **Notas por turma e por assunto**, com histórico auditado de alteração. |
| **Canais** | Grupos de professores no WhatsApp e no Facebook; perfis de "professor que ensina professor" no Instagram e no YouTube; coordenadores pedagógicos (um coordenador traz a escola inteira); indicação (professor convida colega e ganha 1 mês de Pro); parceria com ETECs e escolas da região. |
| **Fontes de receita** | Assinatura mensal pelo Stripe: **Pro R$ 29,90** (professor) e **Escola R$ 199,90** (coordenação). O Free é o funil. |
| **Estrutura de custos** | Infraestrutura: hoje a VM da disciplina (custo zero); em produção comercial, uma VM pequena + storage S3. **API de IA por uso** (gerar questão e ler dissertativa — o principal custo variável, por isso fica no Pro e tem limite). Taxas do Stripe por cobrança. E-mail transacional. Domínio. Tempo de desenvolvimento e suporte. |
| **Métricas-chave** | Cadastros, ativação (1ª prova corrigida por foto em 7 dias), assinantes Pro/Escola, MRR, conversão Free → Pro, churn mensal, folhas corrigidas por mês. |
| **Vantagem injusta** | Banco de questões que cresce com o uso: cada questão aprovada por um professor fica ligada ao trecho do material de onde veio, por disciplina e série — quanto mais professores, melhores as questões sugeridas. Acesso direto a professores e alunos de Fatec/ETEC para testar cedo. Arquitetura já pronta (pagamento, auditoria, storage), que deixa o tempo todo para o problema do professor. |

## 8. Mapa de reaproveitamento

A arquitetura das atividades 1 a 8 foi reaproveitada inteira; só o domínio mudou. O que cada peça virou no ProvaPronta (o que já está no ar na atividade 10 está marcado com ✅):

| Peça da arquitetura | No ProvaPronta |
|---|---|
| Recurso principal (antes vindo de uma API externa, ao vivo) | ✅ **Turmas, alunos, provas e questões** no MySQL, porque o dado é do professor (`db/001_dominio.sql`) |
| Motor de múltipla escolha com gabarito que nunca vai pro cliente antes da hora | ✅ **Questão de múltipla escolha** com gabarito por índice; ✅ **versão B** com questões e alternativas embaralhadas no servidor |
| Coleção pessoal do usuário | Banco de questões do professor (roadmap) |
| Comentários com moderação | Comentário do coordenador numa questão antes de aprovar a prova (roadmap) |
| Microsserviço de login (`auth-service`) | ✅ Conta do professor e do coordenador; cadastro, login, JWT |
| RBAC em escada com `require_papel_minimo` | ✅ `professor` (Free) < `professor_pro` < `coordenador` (Escola) < `admin` |
| Esqueci minha senha + e-mail transacional | ✅ Recuperação de senha com e-mail da marca (Resend, domínio próprio); aviso "provas corrigidas" (roadmap) |
| Auditoria (`log-service` + Redis Streams) | ✅ `turma_criada`, `prova_criada`, `prova_versao_b`, `material_enviado`, `acesso_negado:*`…; `prova_corrigida` e `nota_alterada` (roadmap) |
| Upload em object storage (Garage, S3, bucket privado) | ✅ **PDF da apostila** ligado à prova + foto de perfil; fotos das folhas de resposta (roadmap) |
| URL pré-assinada + repasse pela API (`storage_proxy`) | ✅ Só o dono da prova abre o PDF, por link que expira |
| Validação de arquivo pelos bytes | ✅ PDF conferido pela assinatura `%PDF-`; foto de perfil sem EXIF |
| Plano pago (Stripe: checkout, webhook assinado, troca de papel) | ✅ **Pro** e **Escola**: o webhook troca `professor` → `professor_pro` / `coordenador` |
| Perfil com selo do plano | ✅ Perfil do professor com selo do plano |
| Painel de admin | ✅ Usuários, papéis e eventos de auditoria |
| Swagger / OpenAPI | ✅ API de turmas e provas documentada em `/docs` |
| CI/CD (GitHub Actions + GHCR + GitOps no Portainer) | ✅ Imagens `provapronta-*`, smoke test com turma, prova e PDF |
| Observabilidade (`/health`, `/metrics`, Prometheus, Grafana) | ✅ Painel "ProvaPronta — saúde e métricas"; tempo de correção por folha (roadmap) |

**Infraestrutura:** igual. Mesma stack no Portainer, mesmos serviços, mesmo subdomínio.

## 9. Privacidade (LGPD)

O ProvaPronta trata dados de alunos, muitos deles **menores de idade** — dado que a LGPD manda tratar no melhor interesse da criança e do adolescente. Por isso, desde o plano:
- **Mínimo de dado:** do aluno, só nome, turma e número de chamada. Nada de CPF, e-mail ou foto do aluno.
- **Quem vê:** só o professor da turma (e o coordenador da escola, no plano Escola). A checagem é no backend, pelo papel do JWT — a mesma regra de "só o dono edita o próprio perfil" da atividade 6.
- **Fotos das provas:** bucket privado, abertas só por URL pré-assinada que expira; removidas automaticamente depois do fim do ano letivo.
- **Rastro:** toda leitura e alteração de nota fica no log de auditoria.
- **Material do professor:** o PDF é dele, fica privado e nunca é compartilhado com outros usuários nem usado para gerar prova de outra pessoa.
