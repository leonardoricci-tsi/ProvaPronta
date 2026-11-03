-- ProvaPronta — biblioteca de materiais (PDFs organizados em pastas).
--
-- pastas (dono: usuario_id) ─1:N─ materiais (PDF no Garage)
--
-- Ex.: pasta "1º ano — Matemática — 1º bimestre" com os PDFs da apostila.
-- Na hora de gerar questões, o professor escolhe uma pasta inteira, um PDF
-- ou vários. Aplicado pela migration c3e5a7b9d1f2 (alembic upgrade head).
--
-- O arquivo fica no Garage; aqui só a chave do objeto, o nome original e o
-- tamanho. Apagar a pasta leva os materiais junto (CASCADE) — a API apaga
-- os objetos no Garage antes.

CREATE TABLE pastas (
    id INT NOT NULL AUTO_INCREMENT,
    usuario_id INT NOT NULL,
    nome VARCHAR(150) NOT NULL,
    criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX ix_pastas_usuario_id (usuario_id)
);

CREATE TABLE materiais (
    id INT NOT NULL AUTO_INCREMENT,
    usuario_id INT NOT NULL,
    pasta_id INT NOT NULL,
    nome VARCHAR(255) NOT NULL,
    chave VARCHAR(255) NOT NULL,
    tamanho_bytes INT NOT NULL,
    criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX ix_materiais_usuario_id (usuario_id),
    INDEX ix_materiais_pasta_id (pasta_id),
    CONSTRAINT uq_materiais_chave UNIQUE (chave),
    CONSTRAINT fk_materiais_pasta_id FOREIGN KEY (pasta_id) REFERENCES pastas (id) ON DELETE CASCADE
);
