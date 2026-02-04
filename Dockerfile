FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Disable development dependencies in uv
ENV UV_NO_DEV=1

# Set working directory for all subsequent commands
WORKDIR /app

# Ensure uv has a writable cache directory
ENV XDG_CACHE_HOME=/tmp
ENV UV_CACHE_DIR=/tmp/uv
ENV UV_NO_SYNC=1
RUN mkdir -p /tmp/uv

# Copy project files
COPY . .

# Install using uv
RUN uv sync --locked

ENV APP_MODULE=splash_userservice.api:app
EXPOSE 80

CMD ["uv", "run", "--frozen", "uvicorn", "splash_userservice.api:app", "--host", "0.0.0.0", "--port", "80"]