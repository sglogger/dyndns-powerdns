FROM python:3.12-alpine

ENV TZ=Europe/Zurich

# tzdata für Zeitzone, curl optional für Debug
RUN apk update
RUN apk add --no-cache tzdata curl iputils-ping
RUN apk upgrade

# Non-root user
RUN adduser -D app
USER app

WORKDIR /app

# Deps
COPY --chown=app:app requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App + Entrypoint
COPY --chown=app:app dyndns.py entrypoint.sh .
RUN chmod +x /app/entrypoint.sh

# Healthcheck: prüft, ob IPv4-Endpoint erreichbar ist
HEALTHCHECK --interval=2m --timeout=10s --start-period=20s --retries=3 \
  CMD sh -c "python -c \"import json,urllib.request; json.load(urllib.request.urlopen('https://api4.ipify.org?format=json', timeout=5))\" >/dev/null 2>&1 || exit 1"

ENTRYPOINT ["/app/entrypoint.sh"]

