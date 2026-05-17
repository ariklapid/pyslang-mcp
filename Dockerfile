FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN python -m pip install --upgrade pip \
    && python -m pip install .

RUN useradd --create-home --shell /usr/sbin/nologin pyslang \
    && mkdir -p /workspace \
    && chown pyslang:pyslang /workspace

USER pyslang

EXPOSE 8000

CMD ["pyslang-mcp", "--transport", "streamable-http", "--experimental-enable-http", "--http-host", "0.0.0.0", "--http-port", "8000", "--http-require-bearer-token"]
