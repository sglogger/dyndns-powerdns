#!/usr/bin/env python3
"""
Update dyn.example.net in PowerDNS if public IPv4 changed.

Env vars required:
  PDNS_API_URL     e.g. http://127.0.0.1:8081/api/v1
  PDNS_API_KEY     e.g. s3cr3t
Optional:
  PDNS_SERVER_ID   default: localhost
  PDNS_ZONE        default: example.net
  PDNS_RECORD      default: dyn
  PDNS_TTL         default: 60
"""

import os
import sys
import json
import requests

PDNS_API_URL   = os.getenv("PDNS_API_URL")
PDNS_API_KEY   = os.getenv("PDNS_API_KEY")
PDNS_SERVER_ID = os.getenv("PDNS_SERVER_ID", "localhost")
PDNS_ZONE      = os.getenv("PDNS_ZONE", "exmple.net").rstrip(".")
PDNS_RECORD    = os.getenv("PDNS_RECORD", "dyn").strip(".")
PDNS_TTL       = int(os.getenv("PDNS_TTL", "60"))

if not PDNS_API_URL or not PDNS_API_KEY:
    print("ERROR: PDNS_API_URL and PDNS_API_KEY must be set.", file=sys.stderr)
    sys.exit(2)

HEADERS = {
    "X-API-Key": PDNS_API_KEY,
    "Accept": "application/json",
    "Content-Type": "application/json",
}

session = requests.Session()
session.headers.update(HEADERS)

def get_public_ip_v4(timeout=5):
    r = session.get("https://api4.ipify.org", params={"format":"json"}, timeout=timeout)
    r.raise_for_status()
    return r.json()["ip"]

def fqdn(zone, record):
    return f"{record}.{zone}.".lower()

def get_zone():
    url = f"{PDNS_API_URL}/servers/{PDNS_SERVER_ID}/zones/{PDNS_ZONE}."
    r = session.get(url, timeout=10)
    r.raise_for_status()
    return r.json()

def current_rr_content(zone_json, name, rtype):
    for rr in zone_json.get("rrsets", []):
        if rr.get("name","").lower() == name.lower() and rr.get("type","").upper() == rtype.upper():
            return [rec["content"] for rec in rr.get("records", []) if not rec.get("disabled", False)]
    return []

def patch_rr(name, rtype, contents, ttl):
    url = f"{PDNS_API_URL}/servers/{PDNS_SERVER_ID}/zones/{PDNS_ZONE}."
    payload = {
        "rrsets": [{
            "name": name,
            "type": rtype,
            "ttl": ttl,
            "changetype": "REPLACE",
            "records": [{"content": c, "disabled": False} for c in contents]
        }]
    }
    r = session.patch(url, data=json.dumps(payload), timeout=10)
    r.raise_for_status()

def main():
    record_fqdn = fqdn(PDNS_ZONE, PDNS_RECORD)

    try:
        ipv4 = get_public_ip_v4()
    except Exception as e:
        print(f"ERROR: IPv4 lookup failed: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        zone = get_zone()
    except Exception as e:
        print(f"ERROR: Failed to fetch zone: {e}", file=sys.stderr)
        sys.exit(1)

    current_a = current_rr_content(zone, record_fqdn, "A")

    if current_a != [ipv4]:
        print(f"Updating A {record_fqdn} -> {ipv4} (was: {current_a or 'absent'})")
        try:
            patch_rr(record_fqdn, "A", [ipv4], PDNS_TTL)
            print("DNS updated.")
        except Exception as e:
            print(f"ERROR: Failed to update A: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"No change for A {record_fqdn}: {ipv4}")

if __name__ == "__main__":
    main()

