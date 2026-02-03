FROM python:3.12-slim

# Install uv
RUN pip install --no-cache-dir uv

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

COPY ./ /app
RUN uv sync --frozen

ENV APP_MODULE=splash_userservice.api:app
EXPOSE 80

CMD ["uvicorn", "splash_userservice.api:app", "--host", "0.0.0.0", "--port", "80"]