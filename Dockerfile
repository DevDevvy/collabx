FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends     ca-certificates   && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md /app/
COPY src /app/src

RUN pip install --no-cache-dir -U pip && pip install --no-cache-dir .

EXPOSE 8080
ENV HOST=0.0.0.0
ENV PORT=8080

# Cloud Run injects PORT. Use sh expansion so we listen on ${PORT:-8080}.
CMD ["sh","-c","python -m uvicorn collabx_server.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
