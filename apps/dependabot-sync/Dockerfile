FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

RUN groupadd --system watchback && useradd --system --gid watchback --home-dir /app watchback

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src

USER watchback
CMD ["python", "-m", "watchback_dependabot_sync"]
