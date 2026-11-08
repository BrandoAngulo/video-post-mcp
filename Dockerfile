# Servidor MCP de postproducción (stdio). Lo lanza Claude Desktop con `docker run -i`.

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MEDIA_ROOT=/media \
    FONTS_DIR=/app/fonts
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY fonts ./fonts
RUN pip install --no-cache-dir .

# `docker build --target pruebas .` corre la suite dentro de la imagen.
FROM base AS pruebas
COPY tests ./tests
RUN pip install --no-cache-dir pytest && python -m pytest -q

# Imagen final (objetivo por defecto).
FROM base AS final
RUN useradd --create-home --uid 1000 editor && mkdir -p /media && chown editor /media
USER editor
ENTRYPOINT ["video-post-mcp"]
