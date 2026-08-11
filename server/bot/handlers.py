from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from server.alerts import AlertHub, format_duration
from server.bot import keyboards
from server.config import Settings
from server.db import Database, Endpoint, parse_iso

logger = logging.getLogger(__name__)


def _db(context: ContextTypes.DEFAULT_TYPE) -> Database:
    return context.application.bot_data["db"]


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data["settings"]


def _alerts(context: ContextTypes.DEFAULT_TYPE) -> AlertHub:
    return context.application.bot_data["alerts"]


def allowed(user_id: Optional[int], settings: Settings) -> bool:
    if not settings.allowed_user_ids:
        return True
    return user_id is not None and user_id in settings.allowed_user_ids


async def guard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    settings = _settings(context)
    if not allowed(user.id if user else None, settings):
        if update.effective_message:
            await update.effective_message.reply_text("Доступ запрещён.")
        return False
    if update.effective_chat:
        _alerts(context).register_chat(update.effective_chat.id)
    return True


def fmt_ts(value: Optional[str]) -> str:
    dt = parse_iso(value)
    if not dt:
        return "—"
    local = dt.astimezone()
    return local.strftime("%d.%m.%Y %H:%M:%S")


async def build_endpoints_view(db: Database, settings: Settings) -> tuple[str, object]:
    endpoints = await db.list_endpoints()
    if not endpoints:
        text = (
            "Точек пока нет.\n"
            "Добавьте: <code>/add_point Имя точки</code>\n"
            "или через Admin API."
        )
        return text, keyboards.endpoints_keyboard([])

    items: list[tuple[Endpoint, str]] = []
    lines = ["<b>Точки мониторинга</b>\n"]
    for ep in endpoints:
        status = await db.endpoint_status(ep, settings.offline_threshold_sec)
        items.append((ep, status))
        emoji = keyboards.STATUS_EMOJI.get(status, "⚪")
        host = f" ({ep.hostname})" if ep.hostname else ""
        lines.append(f"{emoji} <b>{ep.name}</b>{host}")
        lines.append(f"   last seen: {fmt_ts(ep.last_seen_at)}")
    return "\n".join(lines), keyboards.endpoints_keyboard(items)


async def build_endpoint_detail(
    db: Database,
    settings: Settings,
    endpoint_id: int,
) -> Optional[tuple[str, object]]:
    ep = await db.get_endpoint(endpoint_id)
    if ep is None:
        return None
    status = await db.endpoint_status(ep, settings.offline_threshold_sec)
    emoji = keyboards.STATUS_EMOJI.get(status, "⚪")
    monitors = await db.list_monitors(ep.id)
    open_incs = await db.get_open_monitor_incidents(ep.id)
    offline = await db.get_open_offline_incident(ep.id)

    lines = [
        f"{emoji} <b>{ep.name}</b>",
        f"Hostname: <code>{ep.hostname or '—'}</code>",
        f"Last seen: {fmt_ts(ep.last_seen_at)}",
        f"Алерты: {'вкл' if ep.alerts_enabled else 'выкл'}",
        "",
        "<b>Мониторы</b>",
    ]
    if not monitors:
        lines.append("ещё не было heartbeat")
    else:
        for m in monitors:
            mark = "🟢" if m.is_connected else "🔴"
            lines.append(f"{mark} {m.name or m.monitor_key}")

    if offline:
        lines.append("")
        lines.append(f"⚫ Агент offline с {fmt_ts(offline.started_at)}")

    if open_incs:
        lines.append("")
        lines.append("<b>Открытые отключения</b>")
        for inc in open_incs:
            started = parse_iso(inc.started_at)
            dur = int((datetime.now(timezone.utc) - started).total_seconds()) if started else None
            lines.append(
                f"🔴 {inc.monitor_name or inc.monitor_key} "
                f"с {fmt_ts(inc.started_at)} ({format_duration(dur)})"
            )

    return "\n".join(lines), keyboards.endpoint_keyboard(ep.id, ep.alerts_enabled)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update, context):
        return
    text, kb = await build_endpoints_view(_db(context), _settings(context))
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update, context):
        return
    since = datetime.now(timezone.utc) - timedelta(days=7)
    rows = await _db(context).stats(since)
    lines = ["<b>Статистика за 7 дней</b>\n"]
    if not rows:
        lines.append("Нет данных.")
    else:
        for row in rows:
            lines.append(
                f"• <b>{row['name']}</b>: {row['incident_count']} откл., "
                f"downtime {format_duration(row['total_downtime_sec'])}"
            )
    await update.effective_message.reply_text(
        "\n".join(lines),
        reply_markup=keyboards.stats_keyboard(),
        parse_mode=ParseMode.HTML,
    )


async def cmd_add_point(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update, context):
        return
    name = " ".join(context.args).strip() if context.args else ""
    if not name:
        await update.effective_message.reply_text("Использование: /add_point Имя точки")
        return
    ep = await _db(context).create_endpoint(name)
    await update.effective_message.reply_text(
        f"Точка <b>{ep.name}</b> создана (id={ep.id}).\n\n"
        f"Токен агента:\n<code>{ep.agent_token}</code>\n\n"
        "Пропишите его в <code>agent/config.json</code>.",
        parse_mode=ParseMode.HTML,
    )


async def cmd_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update, context):
        return
    if len(context.args) < 2:
        await update.effective_message.reply_text(
            "Использование: /alerts &lt;id|имя&gt; on|off",
            parse_mode=ParseMode.HTML,
        )
        return
    target = context.args[0]
    mode = context.args[1].lower()
    if mode not in {"on", "off"}:
        await update.effective_message.reply_text("Режим: on или off")
        return
    endpoints = await _db(context).list_endpoints()
    ep: Optional[Endpoint] = None
    if target.isdigit():
        ep = await _db(context).get_endpoint(int(target))
    else:
        for item in endpoints:
            if item.name.lower() == target.lower():
                ep = item
                break
    if ep is None:
        await update.effective_message.reply_text("Точка не найдена.")
        return
    updated = await _db(context).set_alerts_enabled(ep.id, mode == "on")
    assert updated is not None
    await update.effective_message.reply_text(
        f"Алерты для <b>{updated.name}</b>: {'вкл' if updated.alerts_enabled else 'выкл'}",
        parse_mode=ParseMode.HTML,
    )


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    if not await guard(update, context):
        await query.answer()
        return
    await query.answer()
    data = query.data or ""
    db = _db(context)
    settings = _settings(context)

    if data == "list":
        text, kb = await build_endpoints_view(db, settings)
        await query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    if data.startswith("ep:"):
        endpoint_id = int(data.split(":")[1])
        detail = await build_endpoint_detail(db, settings, endpoint_id)
        if detail is None:
            await query.edit_message_text("Точка не найдена.")
            return
        text, kb = detail
        await query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    if data.startswith("hist:"):
        _, eid, days_s = data.split(":")
        endpoint_id = int(eid)
        days = int(days_s)
        ep = await db.get_endpoint(endpoint_id)
        if ep is None:
            await query.edit_message_text("Точка не найдена.")
            return
        since = datetime.now(timezone.utc) - timedelta(days=days)
        incidents = await db.list_incidents(endpoint_id, since, limit=30)
        lines = [f"<b>{ep.name}</b> — история за {days} дн.\n"]
        if not incidents:
            lines.append("Отключений нет.")
        else:
            for inc in incidents:
                if inc.ended_at and inc.duration_sec is not None:
                    dur = format_duration(inc.duration_sec)
                    state = "закрыто"
                else:
                    started = parse_iso(inc.started_at)
                    dur = format_duration(
                        int((datetime.now(timezone.utc) - started).total_seconds())
                        if started
                        else None
                    )
                    state = "открыто"
                lines.append(
                    f"• {inc.monitor_name or inc.monitor_key}\n"
                    f"  {fmt_ts(inc.started_at)} → {fmt_ts(inc.ended_at)} ({dur}, {state})"
                )
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=keyboards.history_keyboard(endpoint_id),
            parse_mode=ParseMode.HTML,
        )
        return

    if data.startswith("alerts:"):
        _, eid, _ = data.split(":")
        endpoint_id = int(eid)
        ep = await db.get_endpoint(endpoint_id)
        if ep is None:
            await query.edit_message_text("Точка не найдена.")
            return
        await db.set_alerts_enabled(endpoint_id, not ep.alerts_enabled)
        detail = await build_endpoint_detail(db, settings, endpoint_id)
        assert detail is not None
        text, kb = detail
        await query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    if data.startswith("stats:"):
        days = int(data.split(":")[1])
        since = datetime.now(timezone.utc) - timedelta(days=days)
        rows = await db.stats(since)
        lines = [f"<b>Статистика за {days} дн.</b>\n"]
        if not rows:
            lines.append("Нет данных.")
        else:
            for row in rows:
                lines.append(
                    f"• <b>{row['name']}</b>: {row['incident_count']} откл., "
                    f"downtime {format_duration(row['total_downtime_sec'])}"
                )
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=keyboards.stats_keyboard(),
            parse_mode=ParseMode.HTML,
        )


def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("add_point", cmd_add_point))
    app.add_handler(CommandHandler("alerts", cmd_alerts))
    app.add_handler(CallbackQueryHandler(on_callback))
