FROM python:3.11-slim

WORKDIR /app

# Install git for motoko dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy motoko package first (parent directory)
COPY ../ /motoko

# Copy API files
COPY pyproject.toml ./
COPY *.py ./
COPY static/ ./static/

# Install dependencies (motoko is installed from /motoko directory)
RUN cd /motoko && uv sync && cd /app && uv sync

# Create data directory
RUN mkdir -p /data && chmod 777 /data

# Expose port
EXPOSE 8000

# Run the application
ENV PYTHONUNBUFFERED=1

CMD ["sh", "-c", "cd /motoko && uv run --directory /app uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
