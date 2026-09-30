# Harness image with FikoRE, Node.js and the capcsp package.
# FikoRE builds only on Linux; use this image on macOS.
FROM node:22-bookworm-slim AS node

FROM ubuntu:24.04

RUN DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends \
  build-essential \
  ca-certificates \
  git \
  libmnl-dev \
  libnetfilter-queue-dev \
  && rm -rf /var/lib/apt/lists/*

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /pilot
ENV UV_LINK_MODE=copy UV_PYTHON_INSTALL_DIR=/opt/uv-python UV_PROJECT_ENVIRONMENT=/opt/venv

COPY 5g-network-emulator 5g-network-emulator
RUN make -C 5g-network-emulator -j"$(nproc)" bin/fikore

COPY . .
RUN uv sync --frozen

ENTRYPOINT ["uv", "run", "--frozen", "--no-sync"]
CMD ["capcsp", "--help"]
