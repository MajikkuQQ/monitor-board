from __future__ import annotations

import asyncio
import logging
from typing import Optional

from telegram import Bot
from telegram.constants import ParseMode

from server.db import HeartbeatChange

logger = logging.getLogger(__name__)


def format_duration(seconds: Optional[int]) -> str:
    if seconds is None:
        return "?"
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}ч {minutes}м {secs}с"
    if minutes:
        return f"{minutes}м {secs}с"
    return f"{secs}с"


def format_alert(change: HeartbeatChange) -> Optional[str]:
    ep = change.endpoint
    if change.kind == "monitor_offline" and change.monitor:
        name = change.monitor.name or change.monitor.monitor_key
        return (
            f"🔴 <b>{ep.name}</b>\n"
            f"Монитор отключён: <code>{name}</code>"
        )
    if change.kind == "monitor_online" and change.monitor:
        name = change.monitor.name or change.monitor.monitor_key
        return (
            f"🟢 <b>{ep.name}</b>\n"
            f"Монитор снова в сети: <code>{name}</code>\n"
            f"Был выключен: {format_duration(change.duration_sec)}"
        )
    if change.kind == "agent_offline":
        return (
            f"⚫ <b>{ep.name}</b>\n"
            f"Агент не отвечает (нет heartbeat)"
        )
    if change.kind == "agent_online":
        return (
            f"🟢 <b>{ep.name}</b>\n"
            f"Агент снова на связи\n"
            f"Был недоступен: {format_duration(change.duration_sec)}"
        )
    return None


class AlertHub:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[HeartbeatChange] = asyncio.Queue()
        self._chat_ids: set[int] = set()
        self._bot: Optional[Bot] = None
        self._task: Optional[asyncio.Task] = None

    def set_bot(self, bot: Bot) -> None:
        self._bot = bot

    def register_chat(self, chat_id: int) -> None:
        self._chat_ids.add(chat_id)

    async def publish(self, change: HeartbeatChange) -> None:
        if not change.endpoint.alerts_enabled:
            return
        await self.queue.put(change)

    async def publish_many(self, changes: list[HeartbeatChange]) -> None:
        for change in changes:
            await self.publish(change)

    async def start(self, seed_chat_ids: list[int]) -> None:
        self._chat_ids.update(seed_chat_ids)
        self._task = asyncio.create_task(self._worker(), name="alert-worker")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _worker(self) -> None:
        while True:
            change = await self.queue.get()
            try:
                text = format_alert(change)
                if not text or not self._bot or not self._chat_ids:
                    continue
                for chat_id in list(self._chat_ids):
                    try:
                        await self._bot.send_message(
                            chat_id=chat_id,
                            text=text,
                            parse_mode=ParseMode.HTML,
                        )
                    except Exception:
                        logger.exception("Failed to send alert to chat_id=%s", chat_id)
            finally:
                self.queue.task_done()
