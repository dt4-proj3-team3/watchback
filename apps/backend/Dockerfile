FROM node:24-slim AS node-runtime

RUN npm install --global npm@11.12.1

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

RUN groupadd --system watchback \
    && useradd --system --gid watchback --home-dir /app watchback

WORKDIR /app
COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node-runtime /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && npm --version | grep --quiet --line-regexp '11.12.1'
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src

USER watchback
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "watchback_backend.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
