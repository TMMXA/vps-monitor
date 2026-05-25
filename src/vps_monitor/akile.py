from __future__ import annotations

import time
from typing import Any

import httpx

from .config import GIB, AppConfig

BASE_URL = "https://api.akile.ai/api/v1"


class AkileClient:
    def __init__(self, config: AppConfig):
        self.config = config

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Api-Client": self.config.akile_client_id,
            "Api-Secret": self.config.akile_secret,
        }

    async def _get(self, client: httpx.AsyncClient, path: str, params: dict[str, Any] | None = None) -> dict:
        response = await client.get(f"{BASE_URL}{path}", params=params, headers=self.headers)
        response.raise_for_status()
        data = response.json()
        if data.get("status_code") not in (None, 0):
            raise RuntimeError(f"Akile API {path} failed: {data.get('status_msg')}")
        return data

    async def _post(self, client: httpx.AsyncClient, path: str, payload: dict[str, Any]) -> dict:
        response = await client.post(f"{BASE_URL}{path}", json=payload, headers=self.headers)
        response.raise_for_status()
        data = response.json()
        if data.get("status_code") not in (None, 0):
            raise RuntimeError(f"Akile API {path} failed: {data.get('status_msg')}")
        return data

    async def fetch(self) -> list[dict]:
        if not self.config.has_akile_credentials:
            raise RuntimeError("AKILE_CLIENT_ID and AKILE_SECRET are required for collection")

        async with httpx.AsyncClient(timeout=30) as client:
            list_response = await self._post(
                client,
                "/api/server/GetServerList",
                {"page_num": 1, "page_size": 100},
            )
            list_items = list_response.get("list") or []
            by_id = {int(item["id"]): item for item in list_items if item.get("id") is not None}
            servers: list[dict] = []

            for akile_id in self.config.server_ids:
                item = by_id.get(akile_id)
                if item is None:
                    raise RuntimeError(f"Akile server id {akile_id} was not found in GetServerList")

                state_response = await self._get(client, "/api/server/GetServerState", {"id": akile_id})
                statistics_response = await self._get(client, "/api/server/GetServerStatistics", {"id": akile_id})
                status_response = await self._get(client, "/api/server/GetServerStatus", {"id": akile_id})

                servers.append(
                    normalize_server(
                        item,
                        state_response.get("data") or {},
                        status_response.get("data") or {},
                        (statistics_response.get("data") or {}).get("data") or [],
                    )
                )

        return servers


def _int(value: Any, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_server(list_item: dict, state: dict, status: dict, statistics: list[dict]) -> dict:
    akile_id = int(list_item["id"])
    limit = _int((status.get("limits") or {}).get("bandwidth"))
    if not limit:
        limit = int((_float(list_item.get("flow"), 0) or 0) * GIB)

    used = _int((status.get("usages") or {}).get("bandwidth"))
    if used is None:
        used = _int(list_item.get("used_flow"), 0) or 0
    remaining = max(0, limit - used)

    samples = []
    for sample in statistics:
        sample_at = _int(sample.get("time"))
        if not sample_at:
            continue
        samples.append(
            {
                "sample_at": sample_at,
                "netin_bps": _float(sample.get("netin"), 0) or 0,
                "netout_bps": _float(sample.get("netout"), 0) or 0,
                "cpu": _float(sample.get("cpu")),
                "memory_used_bytes": _float(sample.get("mem")),
                "disk_read": _float(sample.get("diskread")),
                "disk_write": _float(sample.get("diskwrite")),
            }
        )

    limits = status.get("limits") or {}
    display_name = list_item.get("server_re_name") or list_item.get("server_name") or status.get("name") or str(akile_id)
    return {
        "id": akile_id,
        "server_id": list_item.get("server_id") or status.get("id"),
        "display_name": display_name,
        "area_name": list_item.get("area_name"),
        "node_name": list_item.get("node_name"),
        "plan_name": list_item.get("plan_name"),
        "system_name": list_item.get("system_name"),
        "status_text": status.get("status"),
        "state": state.get("state"),
        "cpu_cores": _int(limits.get("cpu"), _int(list_item.get("cpu"))),
        "memory_bytes": _int(limits.get("memory"), (_int(list_item.get("memory"), 0) or 0) * 1024 * 1024),
        "disk_bytes": _int(limits.get("disk"), (_int(list_item.get("disk"), 0) or 0) * GIB),
        "rate_mbps": _int(limits.get("rate"), _int(list_item.get("bandwidth"))),
        "traffic_limit_bytes": limit,
        "used_traffic_bytes": used,
        "remaining_traffic_bytes": remaining,
        "due_at": _int(list_item.get("due_time")),
        "next_reset_at": _int(status.get("next_reset_time")),
        "uptime_seconds": _int(state.get("uptime")),
        "updated_at": int(time.time()),
        "realtime": {
            "cpu_used": _float(state.get("cpu_used")),
            "memory_total_bytes": _int(state.get("memory_total")),
            "memory_used_bytes": _int(state.get("memory_used")),
            "netin_total_bytes": _int(state.get("netin")),
            "netout_total_bytes": _int(state.get("netout")),
            "disk_read_total_bytes": _int(state.get("disk_read")),
            "disk_write_total_bytes": _int(state.get("disk_write")),
        },
        "samples": samples,
    }
