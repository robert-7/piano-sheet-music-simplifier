# syntax=docker/dockerfile:1.7

# Piano-Learning container
# Includes: Python runtime, project deps, OpenJDK 17, Audiveris 5.7.1, LilyPond

FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
ARG AUDIVERIS_VERSION=5.7.1

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:/usr/local/bin:${PATH}"

WORKDIR /app

# Base OS packages and tools
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        wget curl gnupg \
        python3 python3-venv python3-pip \
        git \
        openjdk-17-jre-headless \
        lilypond \
        poppler-utils \
        fonts-dejavu-core; \
    rm -rf /var/lib/apt/lists/*

# Create and activate a dedicated virtual environment (PEP 668 compliant)
RUN set -eux; \
    python3 -m venv "$VIRTUAL_ENV"; \
    "$VIRTUAL_ENV/bin/python" -m pip install --upgrade pip

# Install Python dependencies first (leverage Docker layer cache)
COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Install Audiveris 5.7.1 (extract .deb contents to avoid post-install scripts)
RUN set -eux; \
    tmpdeb="/tmp/audiveris.deb"; \
    wget -O "$tmpdeb" "https://github.com/Audiveris/audiveris/releases/download/${AUDIVERIS_VERSION}/Audiveris-${AUDIVERIS_VERSION}-ubuntu24.04-x86_64.deb"; \
    dpkg-deb -x "$tmpdeb" /; \
    ln -sf /opt/audiveris/bin/Audiveris /usr/local/bin/audiveris; \
    rm -f "$tmpdeb"

# Add project files
COPY . .

# Default to a shell; docker-compose will set working dir, user, env, and command.
CMD ["bash"]
