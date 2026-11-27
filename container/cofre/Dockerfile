# Cofre do Jarvis: o único contêiner que lê as senhas (Vaultwarden pelo Bitwarden CLI). Sem volume dos agentes.
FROM node:20-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends python3 ca-certificates tzdata openssl \
 && rm -rf /var/lib/apt/lists/* \
 && npm install -g @bitwarden/cli && npm cache clean --force
ENV TZ=America/Sao_Paulo PYTHONUNBUFFERED=1
COPY broker.py /opt/cofre/broker.py
RUN useradd -m -u 1500 cofre && mkdir -p /segredos-cofre && chown cofre:cofre /segredos-cofre && chmod 700 /segredos-cofre
USER cofre
EXPOSE 8080
CMD ["python3", "/opt/cofre/broker.py"]
