FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends git openssh-client \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN pip install --upgrade pip \
 && pip install .

# Scheduler entrypoint used by the serverdocs-scheduler compose service.
COPY docker/scheduler.sh /usr/local/bin/scheduler.sh
RUN chmod +x /usr/local/bin/scheduler.sh

# Volumes:
#   /config — RO mount with servers.yaml
#   /keys   — RO mount with SSH private keys
#   /data   — RW mount: output tree + known_hosts
VOLUME ["/config", "/keys", "/data"]

ENTRYPOINT ["serverdocs"]
CMD ["--help"]
