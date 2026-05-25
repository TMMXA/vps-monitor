from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from .config import PROJECT_ROOT, AppConfig, load_config
from .flags import FLAG_SVGS
from .storage import Storage
from .service import MonitorService
from .telegram_bot import TelegramCommandBot


config: AppConfig = load_config()
storage = Storage(config.database_path)
service = MonitorService(config, storage)
telegram_bot = TelegramCommandBot(config, storage, service)
scheduler = AsyncIOScheduler(timezone=config.timezone)


def _parse_report_time(value: str) -> tuple[int, int]:
    hour, minute = value.split(":", 1)
    return int(hour), int(minute)


async def _run_job(name: str, func) -> None:
    try:
        result = func()
        if asyncio.iscoroutine(result):
            await result
    except Exception as exc:  # noqa: BLE001 - jobs should never kill the scheduler
        print(f"{name} failed: {exc}")


@asynccontextmanager
async def lifespan(_: FastAPI):
    storage.init(config.hourly_thresholds)
    bot_task: asyncio.Task | None = None

    scheduler.add_job(
        _run_job,
        "interval",
        minutes=config.collect_interval_minutes,
        args=["collect", service.collect],
        id="collect",
        max_instances=1,
        coalesce=True,
    )

    hour, minute = _parse_report_time(config.report_time)
    scheduler.add_job(
        _run_job,
        CronTrigger(hour=hour, minute=minute, timezone=config.timezone),
        args=["report", service.send_report],
        id="daily-report",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _run_job,
        CronTrigger(hour=3, minute=20, timezone=config.timezone),
        args=["cleanup", service.cleanup],
        id="cleanup",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()

    if config.has_akile_credentials:
        asyncio.create_task(_run_job("startup collect", service.collect))
    else:
        print("Akile credentials are not configured; scheduled collection will fail until env vars are set")

    if config.has_telegram_credentials:
        bot_task = asyncio.create_task(telegram_bot.run())
    else:
        print("Telegram credentials are not configured; command polling is disabled")

    yield

    if bot_task:
        bot_task.cancel()
        with suppress(asyncio.CancelledError):
            await bot_task
    scheduler.shutdown(wait=False)


app = FastAPI(title="VPS Monitor", lifespan=lifespan)


def _file(name: str) -> FileResponse:
    path = PROJECT_ROOT / name
    if not path.exists():
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(path)


def _check_admin(authorization: str | None, x_admin_token: str | None) -> None:
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    token = token or x_admin_token
    if not config.admin_token or token != config.admin_token:
        raise HTTPException(status_code=401, detail="invalid admin token")


@app.get("/")
async def index() -> FileResponse:
    return _file("index.html")


@app.get("/app.js")
async def app_js() -> FileResponse:
    return _file("app.js")


@app.get("/styles.css")
async def styles() -> FileResponse:
    return _file("styles.css")


@app.get("/flags/{name}.svg")
async def flag_svg(name: str) -> Response:
    svg = FLAG_SVGS.get(name)
    if svg is None:
        raise HTTPException(status_code=404, detail="flag not found")
    return Response(svg, media_type="image/svg+xml")


@app.get("/api/health")
async def health() -> dict:
    latest = storage.latest_snapshot_time()
    return {
        "ok": True,
        "configured": {
            "akile": config.has_akile_credentials,
            "telegram": config.has_telegram_credentials,
        },
        "serverIds": config.server_ids,
        "lastCollectedAt": latest,
        "lastCollectedAtText": datetime.fromtimestamp(latest, config.timezone).strftime("%Y-%m-%d %H:%M:%S") if latest else None,
        "timezone": config.timezone_name,
    }


@app.get("/api/latest")
async def latest() -> dict:
    latest_collected = storage.latest_snapshot_time()
    return {
        "generatedAt": datetime.now(config.timezone).strftime("%Y-%m-%d %H:%M"),
        "generatedTime": datetime.now(config.timezone).strftime("%H:%M HKT"),
        "lastCollectedAt": latest_collected,
        "lastCollectedAtText": datetime.fromtimestamp(latest_collected, config.timezone).strftime("%Y-%m-%d %H:%M")
        if latest_collected
        else None,
        "servers": storage.latest_servers(config.server_ids, config.timezone),
    }


@app.get("/api/history")
async def history(hours: int = 24) -> dict:
    hours = max(1, min(hours, 168))
    return {
        "hours": hours,
        "servers": [
            {"akileId": akile_id, "hourly": storage.history(akile_id, hours, config.timezone)}
            for akile_id in config.server_ids
        ],
    }


@app.post("/api/collect")
async def collect(
    authorization: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None),
) -> JSONResponse:
    _check_admin(authorization, x_admin_token)
    result = await service.collect()
    return JSONResponse(result)


@app.post("/api/report")
async def report(
    authorization: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None),
) -> JSONResponse:
    _check_admin(authorization, x_admin_token)
    result = await service.send_report()
    return JSONResponse(result)


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception) -> JSONResponse:
    print(f"Unhandled error: {exc}")
    return JSONResponse({"detail": "internal server error"}, status_code=500)
