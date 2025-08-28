# dyndns-powerdns

Small Docker application that periodically discovers your public IPv4 address and updates a record in **PowerDNS Authoritative** via its HTTP API. Ideal if your ISP changes your IP and you want a stable DNS name at home/lab without relying on third-party dynDNS services.

> Checks every 30 minutes by default, and updates only when the IP changed.

---

## Why

- Keep a hostname (e.g. `home.example.com`) pointing at your changing residential IP.
- Avoid exposing dynamic updates (RFC2136) to the internet; update over HTTPS to the PowerDNS API instead.
- Run it anywhere Docker runs.

---

## How it works

1. The container starts a small Python loop (`dyndns.py`).
2. On each cycle it:
   - Fetches your current public IP from a configurable HTTP endpoint (e.g. `https://api4.ipify.org` or https://www.ifconfig.me).
   - Reads the current record in PowerDNS (`A` record by default).
   - If the IP differs, it sends a `PATCH` to the PowerDNS API to upsert the RRset for your zone/record.
3. Sleeps for `CHECK_INTERVAL` seconds (default **1800** = 30 minutes) and repeats.

It only writes when the value changed → fewer journal events and less DNS churn.

---

## Prerequisites

- A **PowerDNS Authoritative** server reachable from where this container runs.
- PowerDNS API enabled and an API key.
  - In `pdns.conf` you’ll typically have:
    ```
    api=yes
    api-key=YOUR_LONG_RANDOM_KEY
    webserver=yes
    webserver-address=0.0.0.0
    webserver-allow-from=0.0.0.0/0   # tighten for your environment - but allow your container! :)
    ```
- A zone you control (e.g. `example.com`) and a record name you want to keep updated (e.g. `home` → `home.example.com`).

> If you use **PowerDNS-Admin**, you can copy the API URL and key from its settings; this tool talks to the PDNS **authoritative API**, not to PowerDNS-Admin itself.

---

## Quick start (docker-compose)

Create a `.env` from the provided example and adjust values:

```bash
cp .env-example .env
# then edit .env
```

`docker-compose.yml` (already in this repo) looks roughly like:

```yaml
services:
  dyndns:
    build: .
    image: mrmouse/dyndns:latest
    container_name: dyndns
    restart: unless-stopped
    # environment data -> see .env file
    environment: 
      PDNS_API_URL: ${PDNS_API_URL}
      PDNS_API_KEY: ${PDNS_API_KEY}
      PDNS_SERVER_ID: ${PDNS_SERVER_ID}
      PDNS_ZONE: ${PDNS_ZONE}
      PDNS_RECORD: ${PDNS_RECORD}

      # Optional (Defaults in Script):
      PDNS_TTL: ${PDNS_TTL}
      INTERVAL_SECONDS: ${INTERVAL_SECONDS}
```

Bring it up:

```bash
docker compose up -d --build
docker compose logs -f dyndns
```

You should see lines indicating the discovered public IP, the current record value, and whether an update was performed.

---

## Docker image & runtime

The `Dockerfile` uses a slim Python base. The entrypoint script runs the Python watcher in a loop. If you see errors like:

```
env: can't execute 'bash': No such file or directory
```

your base image may be `alpine` or another minimal image without `bash`. This project’s entrypoint and compose use `sh` so it works in minimal images. If you customize the image, either install `bash` or keep `/bin/sh` in scripts (see **Troubleshooting**).

Run it without compose:

```bash
docker build -t sglogger/dyndns-powerdns .
docker run --rm -e PDNS_API_URL=http://pdns:8081/api/v1 \
  -e PDNS_API_KEY=changeme \
  -e PDNS_SERVER_ID=localhost \
  -e PDNS_ZONE=example.com. \
  -e PDNS_RECORD=home \
  -e RECORD_TYPE=A \
  -e CHECK_INTERVAL=1800 \
  sglogger/dyndns-powerdns
```

---

## Configuration

### Environment variables

Create a `.env` (there’s an `.env-example` in the repo):

| Variable | Required | Default | Description |
|---|---|---:|---|
| `PDNS_API_URL` | ✅ | — | Base PDNS API, e.g. `http://your-pdns:8081/api/v1` |
| `PDNS_API_KEY` | ✅ | — | PowerDNS API key (from `pdns.conf`) |
| `PDNS_SERVER_ID` | ✅ | `localhost` | Server id in PDNS API path (`/servers/{id}`), often `localhost` |
| `PDNS_ZONE` | ✅ | — | Zone FQDN *with trailing dot*, e.g. `example.com.` |
| `PDNS_RECORD` | ✅ | — | Record label **without** zone, e.g. `home` |
| `RECORD_TYPE` | ❌ | `A` | `A` for IPv4 (current implementation is IPv4-focused). |
| `TTL` | ❌ | `300` | TTL in seconds |
| `CHECK_INTERVAL` | ❌ | `1800` | Seconds between checks (30 min) |
| `IP_DISCOVERY_URL` | ❌ | `https://ifconfig.me/ip` | Endpoint returning caller’s public IPv4 |
| `VERIFY_TLS` | ❌ | `true` | Whether to verify TLS when using `https://` API URLs |
| `LOG_LEVEL` | ❌ | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

> **Note:** `PDNS_ZONE` trailing dot matters for the API payloads. If your zone is `example.com`, use `example.com.`

---

## Local development

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

# Export env for a quick test:
export PDNS_API_URL=http://127.0.0.1:8081/api/v1
export PDNS_API_KEY=changeme
export PDNS_SERVER_ID=localhost
export PDNS_ZONE=example.com.
export PDNS_RECORD=home

python dyndns.py
```

Press `Ctrl+C` to stop; the script runs continuously on its own schedule.

---

## Operational notes

- **Idempotent updates:** The script compares the discovered IP with the current RR value(s) and only writes when different.
- **RRSet semantics:** PowerDNS uses RRsets; the script writes a single-value RRset for your chosen name/type.
- **Multiple records:** If you keep more than one value on that RRset, the script will treat “not equal to the discovered IP” as “needs replace” (single-IP use-case).
- **IPv6:** Current focus is IPv4 (`A`). For IPv6, run a second instance with `RECORD_TYPE=AAAA` and a v6 discovery URL (see **Roadmap**).

---

## Troubleshooting

### Container exits with `env: can't execute 'bash'`
Your base image doesn’t have bash and an entry script tries to use it. The provided `entrypoint.sh` uses `/bin/sh`. If you customized it, either:
- Install bash in the image, or
- Change the shebang to `#!/bin/sh` and avoid bash-isms.

### HTTP 401 / 403 from PowerDNS
- Wrong `PDNS_API_KEY`, wrong `PDNS_API_URL`, or network path blocked.
- Test with:
  ```bash
  curl -H "X-API-Key: $PDNS_API_KEY" "$PDNS_API_URL/servers"
  ```

### HTTP 404 “Zone not found”
- `PDNS_ZONE` must exactly match an existing zone in PDNS (often with trailing dot).
- Check with:
  ```bash
  curl -H "X-API-Key: $PDNS_API_KEY" \
    "$PDNS_API_URL/servers/$PDNS_SERVER_ID/zones/$PDNS_ZONE"
  ```

### 422 / Unprocessable Entity when patching
- Record name/type mismatch, missing trailing dot, or bad RRset payload. Ensure you send the RRset like:
  ```json
  {
    "rrsets": [
      {
        "name": "home.example.com.",
        "type": "A",
        "ttl": 300,
        "changetype": "REPLACE",
        "records": [{"content": "203.0.113.10", "disabled": false}]
      }
    ]
  }
  ```

### IP never changes (always same)
- You might be behind CGNAT; your public IP is shared. This tool can still update to that IP, but inbound port-forwarding may not work.

### Update loop too chatty
- Increase `CHECK_INTERVAL`, and/or keep `LOG_LEVEL=INFO`.

---

## Security considerations

- Treat `PDNS_API_KEY` like a password; keep it in `.env`, not in VCS.
- Restrict the API listener (`webserver-allow-from`) to only the subnets that need access (e.g., your Docker host or a VPN range).
- Prefer `https://` for `PDNS_API_URL` with `VERIFY_TLS=true`.
- If you expose this container publicly, put it behind a firewall; it doesn’t need inbound traffic.

---

## FAQ

**Q: Can I run it for multiple hostnames?**  
A: Yes—run multiple instances with different `PDNS_RECORD` (and optionally different `.env` files / service names).

**Q: Can it update a full wildcard `*.home.example.com`?**  
A: PowerDNS supports wildcard RRs, but dynamic clients typically update a single host. You could set `PDNS_RECORD='*.home'` if that matches your use-case, but most clients expect a concrete name.

**Q: IPv6 support?**  
A: The code is geared to IPv4 discovery and `A` records. You can extend it to discover IPv6 (e.g., hit `https://ifconfig.co` with `Accept: application/json` and use `ip`/`ip6` fields), then run a second instance for `AAAA`.

**Q: Health checks?**  
A: Add a compose `healthcheck:` that ensures DNS resolution returns either your current IP or that PDNS is reachable.

---

## Roadmap / ideas

- Optional IPv6 (`AAAA`) updater.
- Multiple records/hostnames from one process via a small YAML config.
- Pluggable IP discovery backends and retries/jitter.
- Metrics endpoint (Prometheus) for last update, current IP, error count.
- Better structured logging.

---

## License

MIT (suggested). If you prefer another license, update this section and add a `LICENSE` file.

---

## Example `.env`

```dotenv
PDNS_API_URL = "http=//ns.example.net:8081/api/v1"
PDNS_API_KEY = "your-very-secret-api-key"
PDNS_SERVER_ID = "localhost"
PDNS_ZONE = "example.net"
PDNS_RECORD = "dyn"

# Optional (Defaults in Script)=
PDNS_TTL = "60"
INTERVAL_SECONDS = "1800"     # 10 Minuten
```

---

## Logs / Errors

Check with docker logs: `docker logs dyndns`:
````
user@tools:~/docker-containers/dyndns$ docker logs dyndns
[dyndns] Start; INTERVAL_SECONDS=1800
[dyndns] 2025-08-28T21:06:49+02:00 running update...
No change for A dyn.example.net.: 188.63.12.12
[dyndns] Start; INTERVAL_SECONDS=1800
[dyndns] 2025-08-28T21:07:06+02:00 running update...
No change for A dyn.example.net.: 188.63.12.12
[dyndns] 2025-08-28T21:37:06+02:00 running update...
No change for A dyn.example.net.: 188.63.12.12
[dyndns] 2025-08-28T22:07:07+02:00 running update...
No change for A dyn.example.net.: 188.63.12.12
```


---

### Thanks

- PowerDNS team & docs.
- Everyone self-hosting and keeping the internet interesting. 💙
