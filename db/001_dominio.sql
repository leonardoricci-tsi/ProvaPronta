-- ProvaPronta — tabelas do domínio (atividade 10).
--
-- turmas (dono: usuario_id) ─1:N─ alunos
--    └─1:N─ provas (dono: usuario_id) ─1:N─ questoes
--
-- Aplicado pela migration do Alembic (alembic/versions/a7c9e1f3b5d7_dominio_provapronta.py),
-- que registra a versão em alembic_version — é assim que roda em produção
-- (`alembic upgrade head`). Também dá pra aplicar na mão num banco que já
-- tem as tabelas do auth-service: mysql ... < db/001_dominio.sql
--
-- `usuario_id` não tem FOREIGN KEY pra `usuarios` de propósito: a tabela é
-- do auth-service (outro serviço, outro dono); quem garante o dono é o JWT.

CREATE TABLE turmas (
    id INT NOT NULL AUTO_INCREMENT,
    usuario_id INT NOT NULL,
    nome VARCHAR(100) NOT NULL,
    disciplina VARCHAR(100) NOT NULL,
    escola VARCHAR(150) NULL,
    ano_letivo INT NOT NULL,
    criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX ix_turmas_usuario_id (usuario_id)
);

-- Aluno: só nome e número de chamada (LGPD — muitos são menores de idade).
CREATE TABLE alunos (
    id INT NOT NULL AUTO_INCREMENT,
    turma_id INT NOT NULL,
    nome VARCHAR(150) NOT NULL,
    numero_chamada INT NOT NULL,
    PRIMARY KEY (id),
    INDEX ix_alunos_turma_id (turma_id),
    CONSTRAINT uq_aluno_turma_numero UNIQUE (turma_id, numero_chamada),
    CONSTRAINT fk_alunos_turma_id FOREIGN KEY (turma_id) REFERENCES turmas (id) ON DELETE CASCADE
);

-- Prova: o recurso principal. RESTRICT na turma: apagar turma com prova é
-- recusado, em vez de levar as provas junto. O PDF do material fica no
-- Garage; aqui só a chave do objeto e o nome original do arquivo.
CREATE TABLE provas (
    id INT NOT NULL AUTO_INCREMENT,
    usuario_id INT NOT NULL,
    turma_id INT NOT NULL,
    titulo VARCHAR(200) NOT NULL,
    data_aplicacao DATE NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'rascunho',
    material_key VARCHAR(255) NULL,
    material_nome VARCHAR(255) NULL,
    criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX ix_provas_usuario_id (usuario_id),
    INDEX ix_provas_turma_id (turma_id),
    CONSTRAINT fk_provas_turma_id FOREIGN KEY (turma_id) REFERENCES turmas (id) ON DELETE RESTRICT
);

-- Questão de múltipla escolha: alternativas em JSON (lista de textos, na
-- ordem A, B, C...) e o gabarito como índice da alternativa certa.
CREATE TABLE questoes (
    id INT NOT NULL AUTO_INCREMENT,
    prova_id INT NOT NULL,
    ordem INT NOT NULL,
    enunciado TEXT NOT NULL,
    alternativas JSON NOT NULL,
    resposta_correta INT NOT NULL,
    assunto VARCHAR(100) NULL,
    PRIMARY KEY (id),
    INDEX ix_questoes_prova_id (prova_id),
    CONSTRAINT fk_questoes_prova_id FOREIGN KEY (prova_id) REFERENCES provas (id) ON DELETE CASCADE
);
