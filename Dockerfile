# API image. The admin frontend is a separate static build (see DEPLOY.md).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml ./
COPY backend ./backend
RUN pip install . && rm -rf build *.egg-info && useradd --create-home --uid 10001 app

# Migrations run as a separate release step: `alembic upgrade head`.
COPY alembic.ini ./
COPY alembic ./alembic

USER app

ENV ENVIRONMENT=production \
    PORT=8000 \
    # Trust X-Forwarded-For from the platform's proxy so audit logs record the
    # visitor's IP. Only safe when the container is reachable solely through
    # that proxy; otherwise set the proxy's address instead of *.
    FORWARDED_ALLOW_IPS=*

EXPOSE 8000

# One worker: the public-link cache is per process (see cache_service.py).
CMD ["sh", "-c", "exec uvicorn backend.main:app --host 0.0.0.0 --port \"$PORT\" --workers 1 --proxy-headers --forwarded-allow-ips \"$FORWARDED_ALLOW_IPS\""]
