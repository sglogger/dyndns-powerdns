#!/bin/sh
set -eu

# Default: 30 Minuten
: "${INTERVAL_SECONDS:=1800}"

echo "[dyndns] Start; INTERVAL_SECONDS=${INTERVAL_SECONDS}"

term_handler() {
  echo "[dyndns] Caught signal, exiting."
  exit 0
}
trap term_handler TERM INT

while :; do
  timestamp="$(date -Iseconds 2>/dev/null || date)"
  echo "[dyndns] ${timestamp} running update..."
  # Verwende 'python' im python:alpine-Image
  if ! python /app/dyndns.py; then
    echo "[dyndns] run failed (non-zero exit)"
  fi
  sleep "${INTERVAL_SECONDS}"
done
