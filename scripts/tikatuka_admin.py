#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path


BASE_URL = os.getenv("TIKATUKA_ADMIN_BASE_URL", "http://127.0.0.1:8000")
ENV_PATH = Path(os.getenv("TIKATUKA_ADMIN_ENV", "/etc/tikatuka/admin.env"))


def admin_secret() -> str:
    secret = os.getenv("TIKATUKA_ADMIN_SECRET", "").strip()
    if secret:
        return secret
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            if line.startswith("TIKATUKA_ADMIN_SECRET="):
                return line.split("=", 1)[1].strip()
    raise SystemExit("TIKATUKA_ADMIN_SECRET을 찾을 수 없습니다.")


def request_json(path: str) -> dict:
    request = urllib.request.Request(
        BASE_URL.rstrip("/") + path,
        headers={"x-admin-secret": admin_secret()},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode())


def print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else "rooms"
    if command == "rooms":
        print_json(request_json("/api/admin/rooms/summary"))
        return 0
    if command == "streamers":
        print_json(request_json("/api/admin/streamer-rooms"))
        return 0
    if command == "player" and len(argv) > 2:
        nickname = urllib.parse.quote(argv[2])
        print_json(request_json(f"/api/admin/players?nickname={nickname}&limit=20"))
        return 0
    print("사용법: tikatuka_admin.py [rooms|streamers|player 닉네임]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
