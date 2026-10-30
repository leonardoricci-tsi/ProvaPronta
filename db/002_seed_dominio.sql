-- ProvaPronta: dados de demonstração (atividade 10).
--
-- Rodar DEPOIS das migrations (catálogo e auth-service), uma vez:
--   mysql -h HOST -u USUARIO -p BANCO < db/002_seed_dominio.sql
-- ou colar no cliente MySQL. Não roda sozinho em produção de propósito:
-- seed é dado de exemplo, não estrutura.
--
-- Cria a professora da persona do plano de negócio, já no plano Pro, com
-- uma turma, 5 alunos e uma prova de 3 questões:
--   e-mail: marta@provapronta.demo
--   senha:  ProvaPronta2026   (conta de demonstração: troque ou apague
--                              num ambiente de verdade)
-- Pode rodar de novo: apaga e recria só os dados da Marta.

-- Sem isso o cliente mysql pode mandar o texto em latin1 e os acentos
-- chegam corrompidos no banco.
SET NAMES utf8mb4;

SET @email := 'marta@provapronta.demo';

-- Usuária (tabela do auth-service). A senha é o hash bcrypt de
-- "ProvaPronta2026" — nunca a senha em texto.
INSERT INTO usuarios (nome, email, senha_hash, role)
SELECT 'Marta Ribeiro', @email, '$2b$12$MqHRt.YyKSqnUwjPgR5zcut4Ns/Jkd70aGlOIXdEE.vsIegao0scy', 'professor_pro'
WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE email = @email);

SET @marta := (SELECT id FROM usuarios WHERE email = @email);

-- Recomeça do zero (questões e alunos saem em cascata).
DELETE FROM provas WHERE usuario_id = @marta;
DELETE FROM turmas WHERE usuario_id = @marta;

INSERT INTO turmas (usuario_id, nome, disciplina, escola, ano_letivo)
VALUES (@marta, '1º A', 'Biologia', 'E.E. Prof. João Cruz', 2026);
SET @turma := LAST_INSERT_ID();

INSERT INTO alunos (turma_id, nome, numero_chamada) VALUES
    (@turma, 'Ana Beatriz Souza', 1),
    (@turma, 'Bruno Henrique Lima', 2),
    (@turma, 'Carla Mendes', 3),
    (@turma, 'Diego Santos', 4),
    (@turma, 'Eduarda Alves', 5);

INSERT INTO provas (usuario_id, turma_id, titulo, data_aplicacao, status)
VALUES (@marta, @turma, 'Avaliação bimestral — Citologia', '2026-11-20', 'pronta');
SET @prova := LAST_INSERT_ID();

-- resposta_correta é o índice da alternativa certa (0 = A, 1 = B...).
INSERT INTO questoes (prova_id, ordem, enunciado, alternativas, resposta_correta, assunto) VALUES
    (@prova, 1, 'Qual organela é responsável pela respiração celular?',
     JSON_ARRAY('Ribossomo', 'Mitocôndria', 'Complexo de Golgi', 'Lisossomo'), 1, 'Citologia'),
    (@prova, 2, 'A membrana plasmática é formada principalmente por:',
     JSON_ARRAY('Celulose', 'Quitina', 'Fosfolipídios e proteínas', 'Amido'), 2, 'Citologia'),
    (@prova, 3, 'Qual estrutura está presente na célula vegetal e ausente na animal?',
     JSON_ARRAY('Parede celular', 'Núcleo', 'Mitocôndria', 'Ribossomo'), 0, 'Citologia');

INSERT INTO provas (usuario_id, turma_id, titulo, status)
VALUES (@marta, @turma, 'Recuperação — Citologia', 'rascunho');
