# Multi-stage Dockerfile for Agentic AI Workflow Platform
# Optimized for minimal image footprint and non-root execution

FROM python:3.13-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final Runtime Image
FROM python:3.13-slim AS runtime

WORKDIR /app

# Create non-root user
RUN addgroup --system appgroup && adduser --system --group appuser

# Copy installed python dependencies from builder
COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH

# Copy application code, fixtures, and documentation
COPY app/ ./app/
COPY data/ ./data/
COPY pytest.ini requirements.txt .env.example ./

# Ensure data directories are writable by appuser
RUN mkdir -p /app/data && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

ENV APP_ENV=production
ENV APP_DEBUG=false
ENV HOST=0.0.0.0
ENV PORT=8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import httpx; res = httpx.get('http://127.0.0.1:8000/api/v1/health'); exit(0 if res.status_code == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
