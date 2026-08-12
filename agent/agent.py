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
STATE_PATH = BASE_DIR / "state.json"
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
    cfg.setdefault("off_debounce_checks", 6)
    cfg.setdefault("startup_grace_sec", 180)
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


def load_cached_monitors() -> list[dict[str, str]]:
    if not STATE_PATH.exists():
        return []
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        monitors = data.get("monitors") or []
        if not isinstance(monitors, list):
            return []
        out: list[dict[str, str]] = []
        for item in monitors:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or "").strip()
            name = str(item.get("name") or key).strip()
            if key:
                out.append({"key": key, "name": name})
        return out
    except Exception:
        logging.getLogger("agent").exception("Failed to read %s", STATE_PATH)
        return []


def save_cached_monitors(monitors: list[dict[str, str]]) -> None:
    if not monitors:
        return
    payload = {
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "monitors": monitors,
    }
    STATE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


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
    off_debounce_checks = max(
        debounce_checks, int(cfg.get("off_debounce_checks", 6))
    )
    startup_grace_sec = max(0, int(cfg.get("startup_grace_sec", 180)))

    log.info(
        "Agent started (DDC/CI). server=%s host=%s interval=%ss "
        "debounce=%s off_debounce=%s grace=%ss dir=%s",
        cfg["server_url"],
        hostname,
        interval,
        debounce_checks,
        off_debounce_checks,
        startup_grace_sec,
        BASE_DIR,
    )

    cached = load_cached_monitors()
    if cached:
        log.info("Loaded cached monitors: %s", len(cached))
        for m in cached:
            log.info("  CACHED %s (%s)", m["name"], m["key"])

    # Пока DDC после reboot «молчит», не считаем мониторы выключенными.
    grace_deadline = time.time() + startup_grace_sec
    confirmed = list(cached)
    while True:
        live = list_monitors_payload()
        if live:
            confirmed = live
            save_cached_monitors(confirmed)
            log.info("Initial powered-on monitors: %s", len(confirmed))
            for m in confirmed:
                log.info("  ON %s (%s)", m["name"], m["key"])
            break
        if time.time() >= grace_deadline:
            log.warning(
                "Startup grace ended with no DDC ON monitors; "
                "keeping cached=%s",
                len(confirmed),
            )
            break
        log.info(
            "Waiting for DDC (grace %.0fs left), cached=%s",
            max(0, grace_deadline - time.time()),
            len(confirmed),
        )
        if confirmed:
            try:
                send_heartbeat(cfg, hostname, confirmed)
                log.info("Heartbeat ok (grace, cached), powered_on=%s", len(confirmed))
            except Exception:
                log.exception("Heartbeat failed during grace")
        time.sleep(interval)

    pending_keys: Optional[frozenset[str]] = None
    pending_payload: list[dict[str, str]] = list(confirmed)
    pending_count = 0

    while True:
        try:
            current = list_monitors_payload()
            keys = monitor_keys(current)
            confirmed_keys = monitor_keys(confirmed)

            if keys == pending_keys:
                pending_count += 1
            else:
                pending_keys = keys
                pending_payload = current
                pending_count = 1

            needed = (
                off_debounce_checks
                if len(pending_payload) < len(confirmed)
                else debounce_checks
            )

            # Пустой DDC сразу после старта часто ложный — не подтверждаем
            # «все выключены», пока не вышел grace (на случай долгого boot).
            in_grace = time.time() < grace_deadline
            empty_during_grace = in_grace and not pending_payload and confirmed

            if (
                not empty_during_grace
                and pending_count >= needed
                and keys != confirmed_keys
            ):
                log.info(
                    "State confirmed after %s checks: %s -> %s monitors ON",
                    pending_count,
                    len(confirmed),
                    len(pending_payload),
                )
                confirmed = list(pending_payload)
                if confirmed:
                    save_cached_monitors(confirmed)

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
