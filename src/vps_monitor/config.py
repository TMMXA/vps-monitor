from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

GIB = 1024 ** 3
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _server_ids() -> list[int]:
    raw = os.getenv("SERVER_IDS", "")
    if not raw.strip():
        return []
    return [int(item) for item in _split_csv(raw)]


def _chat_ids() -> list[str]:
    return _split_csv(os.getenv("TELEGRAM_CHAT_IDS") or os.getenv("CHAT_ID", ""))


def _thresholds(server_ids: list[int]) -> dict[int, int]:
    result: dict[int, int] = {}
    for server_id in server_ids:
        env_name = f"THRESHOLD_{server_id}_GIB_PER_HOUR"
        gib = float(os.getenv(env_name, "5"))
        result[server_id] = int(gib * GIB)
    return result


@dataclass(frozen=True)
class AppConfig:
    akile_client_id: str
    akile_secret: str
    telegram_bot_token: str
    telegram_chat_ids: list[str]
    telegram_proxy_url: str
    admin_token: str
    server_ids: list[int]
    collect_interval_minutes: int
    report_time: str
    timezone_name: str
    retention_days: int
    database_path: Path
    report_dir: Path
    web_port: int
    hourly_thresholds: dict[int, int]

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone_name)

    @property
    def has_akile_credentials(self) -> bool:
        return bool(self.akile_client_id and self.akile_secret)

    @property
    def has_telegram_credentials(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_ids)


def load_config() -> AppConfig:
    server_ids = _server_ids()
    database_path = Path(os.getenv("DATABASE_PATH", "/data/vps-monitor.sqlite3"))
    return AppConfig(
        akile_client_id=os.getenv("AKILE_CLIENT_ID", ""),
        akile_secret=os.getenv("AKILE_SECRET", ""),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TG_TOKEN", ""),
        telegram_chat_ids=_chat_ids(),
        telegram_proxy_url=os.getenv("TELEGRAM_PROXY") or os.getenv("TG_PROXY", ""),
        admin_token=os.getenv("ADMIN_TOKEN", ""),
        server_ids=server_ids,
        collect_interval_minutes=int(os.getenv("COLLECT_INTERVAL_MINUTES", "30")),
        report_time=os.getenv("REPORT_TIME", "09:00"),
        timezone_name=os.getenv("TZ", "Asia/Hong_Kong"),
        retention_days=int(os.getenv("RETENTION_DAYS", "90")),
        database_path=database_path,
        report_dir=Path(os.getenv("REPORT_DIR", str(database_path.parent / "reports"))),
        web_port=int(os.getenv("PORT", "8000")),
        hourly_thresholds=_thresholds(server_ids),
    )
