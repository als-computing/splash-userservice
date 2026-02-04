FROM python:3.12-slim

# Install uv
RUN pip install --no-cache-dir uv

# Set working directory
WORKDIR /app

# Ensure uv has a writable cache directory
ENV XDG_CACHE_HOME=/tmp
ENV UV_CACHE_DIR=/tmp/uv
ENV UV_NO_SYNC=1
RUN mkdir -p /tmp/uv

# Copy project files
COPY . .

# Install dependencies with uv
RUN uv sync --frozen --no-dev

ENV APP_MODULE=splash_userservice.api:app
EXPOSE 80

CMD ["uv", "run", "--frozen", "uvicorn", "splash_userservice.api:app", "--host", "0.0.0.0", "--port", "80"]