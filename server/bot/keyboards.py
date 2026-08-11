from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from server.db import Endpoint


STATUS_EMOJI = {
    "ok": "🟢",
    "monitor_offline": "🔴",
    "agent_offline": "⚫",
    "unknown": "⚪",
}


def endpoints_keyboard(
    endpoints: list[tuple[Endpoint, str]],
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for endpoint, status in endpoints:
        emoji = STATUS_EMOJI.get(status, "⚪")
        rows.append(
            [
                InlineKeyboardButton(
                    f"{emoji} {endpoint.name}",
                    callback_data=f"ep:{endpoint.id}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton("📊 Статистика 7д", callback_data="stats:7"),
            InlineKeyboardButton("🔄 Обновить", callback_data="list"),
        ]
    )
    return InlineKeyboardMarkup(rows)


def endpoint_keyboard(endpoint_id: int, alerts_enabled: bool) -> InlineKeyboardMarkup:
    alert_label = "🔔 Алерты: вкл" if alerts_enabled else "🔕 Алерты: выкл"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("История сегодня", callback_data=f"hist:{endpoint_id}:1"),
                InlineKeyboardButton("7 дней", callback_data=f"hist:{endpoint_id}:7"),
            ],
            [
                InlineKeyboardButton("30 дней", callback_data=f"hist:{endpoint_id}:30"),
                InlineKeyboardButton(alert_label, callback_data=f"alerts:{endpoint_id}:toggle"),
            ],
            [InlineKeyboardButton("◀️ К списку", callback_data="list")],
        ]
    )


def history_keyboard(endpoint_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("◀️ К точке", callback_data=f"ep:{endpoint_id}"),
                InlineKeyboardButton("К списку", callback_data="list"),
            ]
        ]
    )


def stats_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Сегодня", callback_data="stats:1"),
                InlineKeyboardButton("7 дней", callback_data="stats:7"),
                InlineKeyboardButton("30 дней", callback_data="stats:30"),
            ],
            [InlineKeyboardButton("◀️ К списку", callback_data="list")],
        ]
    )
