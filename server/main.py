from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from telegram.ext import Application

from server.alerts import AlertHub
from server.api import router
from server.bot.handlers import register_handlers
from server.config import get_settings
from server.db import Database
from server.web import mount_web

logging.basicConfig(
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def offline_watcher(db: Database, alerts: AlertHub, threshold_sec: int) -> None:
    while True:
        try:
            changes = await db.mark_stale_endpoints_offline(threshold_sec)
            if changes:
                await alerts.publish_many(changes)
        except Exception:
            logger.exception("Offline watcher failed")
        await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    db = Database(settings.database_path)
    await db.connect()

    alerts = AlertHub()
    tg_app = (
        Application.builder()
        .token(settings.telegram_token)
        .base_url(f"{settings.telegram_api_base}/bot")
        .base_file_url(f"{settings.telegram_api_base}/file/bot")
        .build()
    )
    tg_app.bot_data["db"] = db
    tg_app.bot_data["settings"] = settings
    tg_app.bot_data["alerts"] = alerts
    register_handlers(tg_app)

    alerts.set_bot(tg_app.bot)
    await alerts.start(settings.allowed_user_ids)

    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling(drop_pending_updates=True)

    watcher = asyncio.create_task(
        offline_watcher(db, alerts, settings.offline_threshold_sec),
        name="offline-watcher",
    )

    app.state.db = db
    app.state.alerts = alerts
    app.state.admin_api_key = settings.admin_api_key
    app.state.settings = settings
    app.state.tg_app = tg_app
    app.state.watcher = watcher

    logger.info(
        "Server started on %s:%s (web + telegram)",
        settings.host,
        settings.port,
    )
    try:
        yield
    finally:
        watcher.cancel()
        try:
            await watcher
        except asyncio.CancelledError:
            pass
        await alerts.stop()
        await tg_app.updater.stop()
        await tg_app.stop()
        await tg_app.shutdown()
        await db.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Monitor Board", lifespan=lifespan)
    # Session middleware + static + HTML routes
    mount_web(app, settings)
    app.include_router(router)
    return app


app = create_app()


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "server.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
