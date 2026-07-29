# syntax=docker/dockerfile:1

# Piano-Learning container
# Includes: Python runtime, project deps, OpenJDK, Audiveris, LilyPond

# Stay on 24.04 until Audiveris ships a matching deb: the -ubuntu24.04- build is
# extracted with dpkg-deb -x (no OS checks), but under Apple Silicon's amd64
# emulation the newer tar in 26.04 hits an ENOSYS syscall and the extract fails.
FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
ARG AUDIVERIS_VERSION=5.11.0

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv \
    QT_QPA_PLATFORM=offscreen \
    PATH="/opt/venv/bin:/usr/local/bin:${PATH}" \
    # Where Audiveris' bundled Tesseract looks for OCR language data.
    TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata

WORKDIR /app

# Base OS packages and tools
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        wget curl gnupg \
        python3 python3-venv python3-pip \
        git \
        openjdk-21-jre-headless \
        lilypond \
        musescore \
        poppler-utils \
        tesseract-ocr-eng \
        libgtk-3-0t64 \
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

# Install Audiveris (version pinned by AUDIVERIS_VERSION; extract .deb contents
# with dpkg-deb -x to avoid post-install scripts). The -ubuntu24.04- asset
# matches the base image above; it is the newest Linux build Audiveris ships.
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
