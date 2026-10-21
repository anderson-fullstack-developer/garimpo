FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
# Python com várias threads no Linux: menos "arenas" do malloc = muito menos memória presa sem uso.
ENV MALLOC_ARENA_MAX=2
WORKDIR /srv

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app

# Uma única cópia da API: o monitor de alertas roda dentro dela (duas cópias duplicariam os avisos).
# A cada publicação aplica as migrações do banco (o Alembic usa a conexão direta da Neon) e inicia.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
