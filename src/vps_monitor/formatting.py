from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

GIB = 1024 ** 3


def format_gib(bytes_value: float | int | None, *, trim: bool = True) -> str:
    if bytes_value is None:
        return "-"
    value = float(bytes_value) / GIB
    if trim and abs(value - round(value)) < 0.005:
        return f"{round(value):.0f} GiB"
    return f"{value:.2f} GiB"


def format_percent(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}%"


def format_datetime(timestamp: int | None, tz: ZoneInfo) -> str:
    if not timestamp:
        return "-"
    return datetime.fromtimestamp(int(timestamp), tz).strftime("%Y-%m-%d %H:%M")


def format_uptime(seconds: int | None) -> str:
    if seconds is None:
        return "-"
    seconds = int(seconds)
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    if days:
        return f"{days}天 {hours}小时"
    return f"{hours}小时"


def hour_label(timestamp: int, tz: ZoneInfo) -> str:
    return datetime.fromtimestamp(int(timestamp), tz).strftime("%H")


def flag_for_area(area_name: str | None, node_name: str | None) -> dict[str, str]:
    text = f"{area_name or ''} {node_name or ''}".lower()
    if "澳门" in text or "macau" in text or "mo" in text:
        return {
            "flag": "🇲🇴",
            "flagLabel": "Macau",
            "flagSrc": "/flags/mo.svg",
        }
    if "美国" in text or "lax" in text or "us" in text or "america" in text:
        return {
            "flag": "🇺🇸",
            "flagLabel": "United States",
            "flagSrc": "/flags/us.svg",
        }
    return {
        "flag": "🏳️",
        "flagLabel": "Unknown",
        "flagSrc": "/flags/unknown.svg",
    }
