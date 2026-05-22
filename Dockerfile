FROM python:3.11-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates git \
    && curl -fsSL "https://download.docker.com/linux/static/stable/x86_64/docker-26.1.4.tgz" \
        | tar -xz -C /tmp \
    && mv /tmp/docker/docker /usr/local/bin/docker \
    && curl -fsSL "https://github.com/docker/compose/releases/download/v2.27.1/docker-compose-linux-x86_64" \
        -o /usr/local/bin/docker-compose \
    && chmod +x /usr/local/bin/docker /usr/local/bin/docker-compose \
    && docker --version \
    && /usr/local/bin/docker-compose version \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt VERSION ./
RUN pip install --no-cache-dir -r requirements.txt

COPY config ./config
COPY core ./core
COPY sentinel ./sentinel
COPY tools ./tools
COPY scripts ./scripts/
RUN chmod +x /app/scripts/*.sh /app/scripts/trigger-update.py 2>/dev/null || true
COPY run.sh ./

RUN mkdir -p /app/data

ENV PYTHONUNBUFFERED=1
ENV NODE_EXECUTABLE=/usr/bin/node
ENV HOST=0.0.0.0
ENV PORT=8766

EXPOSE 8766

HEALTHCHECK --interval=30s --timeout=8s --start-period=20s --retries=3 \
    CMD curl -f "http://127.0.0.1:${PORT}/api/admin/health" || exit 1

CMD ["sh", "/app/scripts/docker-entrypoint.sh"]
