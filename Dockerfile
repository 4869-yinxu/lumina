FROM python:3.12-slim

WORKDIR /app

# Node（用于 stdio MCP server，如 @snowluma/mcp）
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY lumina ./lumina
RUN pip install --no-cache-dir .

CMD ["python", "-m", "lumina.main"]
