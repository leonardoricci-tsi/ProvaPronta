# Garage com o garage.toml já dentro da imagem (atividade 6). No compose
# local daria pra montar o arquivo como volume, mas no Portainer não existe
# o repositório pra montar — então é imagem própria, igual aos outros
# serviços (ghcr.io/leonardoricci-tsi/provapronta-garage). O toml não tem segredo:
# rpc_secret e chave S3 entram por variável de ambiente.
FROM dxflrs/garage:v2.3.0

COPY garage.toml /etc/garage.toml

CMD ["/garage", "server", "--single-node", "--default-bucket"]
