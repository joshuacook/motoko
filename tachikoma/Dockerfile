# Tachikoma - Workspace Maintenance Agent
# Analyzes workspaces and creates cleanup decisions in lake/decisions/

FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy and install package
COPY pyproject.toml /app/
COPY src/ /app/src/

RUN pip install --no-cache-dir -e .

# Workspace will be mounted here
VOLUME /workspace

# Environment variables
ENV ANTHROPIC_API_KEY=""
ENV WORKSPACE_PATH="/workspace"
ENV CLEANUP_MODE="schema"

# Entry point
ENTRYPOINT ["tachikoma", "-w", "/workspace", "-m"]
CMD ["schema"]
