FROM python:3.12-slim

# Install uv
RUN pip install --no-cache-dir uv

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Install dependencies with uv
RUN uv sync --frozen --no-dev

ENV APP_MODULE=splash_userservice.api:app
EXPOSE 80

CMD ["uv", "run", "uvicorn", "splash_userservice.api:app", "--host", "0.0.0.0", "--port", "80"]