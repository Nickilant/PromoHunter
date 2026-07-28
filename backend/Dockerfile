# --- base: зависимости в /opt/venv, непривилегированный пользователь ---
FROM python:3.12-slim AS base
ARG UID=1000
ARG GID=1000
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

RUN groupadd -g ${GID} app || true \
 && useradd -m -u ${UID} -g ${GID} app \
 && python -m venv /opt/venv \
 && chown -R ${UID}:${GID} /opt/venv

WORKDIR /app
COPY requirements.txt ./
RUN /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

COPY entrypoint.sh /entrypoint.sh
# sed: страховка от CRLF после checkout на Windows — иначе ломается шебанг
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

USER app
ENTRYPOINT ["/entrypoint.sh"]

# --- dev: код приходит bind-mount'ом, uvicorn --reload из compose ---
FROM base AS dev
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# --- prod: код копируется в образ, несколько воркеров ---
FROM base AS prod
COPY --chown=app:app . /app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
