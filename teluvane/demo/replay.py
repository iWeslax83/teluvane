# teluvane/demo/replay.py
"""Offline demo path: replays demo/fallback_log.jsonl into the running ingest service
so the dashboard/feed/evidence/tamper showcase work WITHOUT an API key.
Usage: python -m teluvane.demo.replay   (ingest must be running on :8900)"""

import json
import os

import httpx

BASE = os.environ.get("TELUVANE_URL", "http://localhost:8900")
HERE = os.path.dirname(__file__)


def main():
    path = os.path.join(HERE, "fallback_log.jsonl")
    n = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            httpx.post(f"{BASE}/events", json=json.loads(line), timeout=10).raise_for_status()
            n += 1
    print(f"replayed {n} events to {BASE}")


if __name__ == "__main__":
    main()
