# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import logging
import socket
import sys
import time
from pathlib import Path
from typing import Any, Optional

import httpx

from monitors import list_monitors_payload


def app_dir() -> Path:
    """Папка с exe (PyInstaller) или с agent.py."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE_DIR = app_dir()
CONFIG_PATH = BASE_DIR / "config.json"
LOG_PATH = BASE_DIR / "agent.log"


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        example = BASE_DIR / "config.example.json"
        raise FileNotFoundError(
            f"Не найден {CONFIG_PATH}. "
            f"Запустите MonitorAgentSetup.exe или скопируйте {example.name} → config.json."
        )
    with CONFIG_PATH.open(encoding="utf-8") as fh:
        cfg = json.load(fh)
    for key in ("server_url", "agent_token"):
        if not cfg.get(key):
            raise ValueError(f"В config.json обязательно поле {key}")
    cfg.setdefault("poll_interval_sec", 5)
    cfg.setdefault("debounce_checks", 3)
    cfg.setdefault("request_timeout_sec", 10)
    cfg.setdefault("hostname", None)
    return cfg


def resolve_hostname(cfg: dict[str, Any]) -> str:
    custom = cfg.get("hostname")
    if custom:
        return str(custom)
    try:
        return socket.gethostname()
    except Exception:
        return "mini-pc"


def monitor_keys(monitors: list[dict[str, str]]) -> frozenset[str]:
    return frozenset(m["key"] for m in monitors)


def send_heartbeat(
    cfg: dict[str, Any],
    hostname: str,
    monitors: list[dict[str, str]],
) -> None:
    url = cfg["server_url"].rstrip("/") + "/api/v1/heartbeat"
    headers = {"Authorization": f"Bearer {cfg['agent_token']}"}
    payload = {
        "hostname": hostname,
        "monitors": monitors,
    }
    timeout = float(cfg.get("request_timeout_sec", 10))
    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()


def main() -> None:
    setup_logging()
    log = logging.getLogger("agent")
    cfg = load_config()
    hostname = resolve_hostname(cfg)
    interval = max(3, int(cfg.get("poll_interval_sec", 5)))
    debounce_checks = max(1, int(cfg.get("debounce_checks", 3)))

    log.info(
        "Agent started (DDC/CI). server=%s host=%s interval=%ss debounce=%s dir=%s",
        cfg["server_url"],
        hostname,
        interval,
        debounce_checks,
        BASE_DIR,
    )

    confirmed = list_monitors_payload()
    log.info("Initial powered-on monitors: %s", len(confirmed))
    for m in confirmed:
        log.info("  ON %s (%s)", m["name"], m["key"])

    pending_keys: Optional[frozenset[str]] = None
    pending_payload: list[dict[str, str]] = confirmed
    pending_count = 0

    while True:
        try:
            current = list_monitors_payload()
            keys = monitor_keys(current)

            if keys == pending_keys:
                pending_count += 1
            else:
                pending_keys = keys
                pending_payload = current
                pending_count = 1

            if (
                pending_count >= debounce_checks
                and keys != monitor_keys(confirmed)
            ):
                log.info(
                    "State confirmed after %s checks: %s -> %s monitors ON",
                    debounce_checks,
                    len(confirmed),
                    len(pending_payload),
                )
                confirmed = list(pending_payload)

            send_heartbeat(cfg, hostname, confirmed)
            log.info(
                "Heartbeat ok, powered_on=%s (raw_now=%s)",
                len(confirmed),
                len(current),
            )
        except Exception:
            log.exception("Heartbeat / DDC probe failed")
        time.sleep(interval)


if __name__ == "__main__":
    main()
