FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates curl gnupg unixodbc \
    && . /etc/os-release \
    && curl --fail --silent --show-error --location \
        "https://packages.microsoft.com/config/debian/${VERSION_ID}/packages-microsoft-prod.deb" \
        --output /tmp/packages-microsoft-prod.deb \
    && dpkg -i /tmp/packages-microsoft-prod.deb \
    && rm /tmp/packages-microsoft-prod.deb \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install --yes --no-install-recommends msodbcsql18 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system watchback \
    && useradd --system --gid watchback --home-dir /app watchback

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src

USER watchback
CMD ["python", "-m", "watchback_gold_sync"]
