from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import httpx

from .config import AppConfig
from .formatting import format_datetime
from .service import MonitorService
from .storage import Storage


HELP_TEXT = """VPS 监控命令
/status - 查看两台 VPS 当前状态
/report - 生成并发送日报截图
/collect - 立刻采集一次 Akile 数据
/history - 查看最近 24 小时流量汇总
/health - 查看服务健康状态
/help - 显示这份帮助"""


class TelegramCommandBot:
    def __init__(self, config: AppConfig, storage: Storage, service: MonitorService):
        self.config = config
        self.storage = storage
        self.service = service
        self._offset: int | None = None

    @property
    def _base_url(self) -> str:
        return f"https://api.telegram.org/bot{self.config.telegram_bot_token}"

    async def run(self) -> None:
        if not self.config.has_telegram_credentials:
            print("Telegram command polling is disabled; Telegram is not configured")
            return

        while True:
            try:
                async with httpx.AsyncClient(timeout=35, proxy=self.config.telegram_proxy_url or None) as client:
                    await self._register_commands(client)
                    await self._drop_pending_updates(client)
                    print("Telegram command polling started")

                    while True:
                        updates = await self._get_updates(client)
                        for update in updates:
                            self._offset = int(update["update_id"]) + 1
                            await self._handle_update(update)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - polling should recover from transient API errors
                print(f"Telegram polling failed; retrying in 30s: {exc}")
                await asyncio.sleep(30)

    async def _register_commands(self, client: httpx.AsyncClient) -> None:
        commands = [
            {"command": "status", "description": "查看 VPS 当前状态"},
            {"command": "report", "description": "生成并发送日报截图"},
            {"command": "collect", "description": "立刻采集一次 Akile 数据"},
            {"command": "history", "description": "查看 24 小时流量汇总"},
            {"command": "health", "description": "查看服务健康状态"},
            {"command": "help", "description": "显示帮助"},
        ]
        await client.post(f"{self._base_url}/setMyCommands", json={"commands": commands})

    async def _drop_pending_updates(self, client: httpx.AsyncClient) -> None:
        response = await client.post(
            f"{self._base_url}/getUpdates",
            json={"offset": -1, "timeout": 0, "allowed_updates": ["message"]},
        )
        response.raise_for_status()
        updates = response.json().get("result", [])
        if updates:
            self._offset = int(updates[-1]["update_id"]) + 1

    async def _get_updates(self, client: httpx.AsyncClient) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {"timeout": 25, "allowed_updates": ["message"]}
        if self._offset is not None:
            payload["offset"] = self._offset
        response = await client.post(f"{self._base_url}/getUpdates", json=payload)
        response.raise_for_status()
        return response.json().get("result", [])

    async def _handle_update(self, update: dict[str, Any]) -> None:
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = str(chat.get("id") or "")
        if chat_id not in {str(item) for item in self.config.telegram_chat_ids}:
            return

        text = (message.get("text") or "").strip()
        if not text.startswith("/"):
            return

        command = text.split(maxsplit=1)[0].split("@", 1)[0].lower()
        try:
            if command in {"/start", "/help"}:
                await self._send(chat_id, HELP_TEXT)
            elif command == "/status":
                await self._send(chat_id, self._status_text())
            elif command == "/health":
                await self._send(chat_id, self._health_text())
            elif command == "/history":
                await self._send(chat_id, self._history_text())
            elif command == "/collect":
                await self._collect(chat_id)
            elif command == "/report":
                await self._report(chat_id)
            else:
                await self._send(chat_id, "未知命令，发送 /help 查看可用命令。")
        except Exception as exc:  # noqa: BLE001 - command errors should be reported to the requester
            await self._send(chat_id, f"命令执行失败：{exc}")

    async def _send(self, chat_id: str, text: str) -> None:
        await self.service.telegram.send_message(text, chat_ids=[chat_id])

    def _status_text(self) -> str:
        servers = self.storage.latest_servers(self.config.server_ids, self.config.timezone)
        last_collected = self.storage.latest_snapshot_time()
        if not servers:
            return "暂无 VPS 数据，可以发送 /collect 先采集一次。"

        lines = [
            "VPS 当前状态",
            f"最后采集：{format_datetime(last_collected, self.config.timezone)}",
        ]
        for server in servers:
            lines.extend(
                [
                    "",
                    f"{server['flag']} {server['name']}",
                    f"剩余：{server['remaining']} / {server['total']}",
                    f"已用：{server['used']} ({server['usedPercent']})",
                    f"预计可用：{server['forecast']}",
                    f"运行时长：{server['uptime']}",
                    f"重置：{server['resetAt']}",
                    f"到期：{server['expiresAt']}",
                ]
            )
        return "\n".join(lines)

    def _health_text(self) -> str:
        latest = self.storage.latest_snapshot_time()
        return "\n".join(
            [
                "VPS Monitor 健康状态",
                "状态：OK",
                f"Akile：{'已配置' if self.config.has_akile_credentials else '未配置'}",
                f"Telegram：{'已配置' if self.config.has_telegram_credentials else '未配置'}",
                f"服务器 ID：{', '.join(str(item) for item in self.config.server_ids)}",
                f"最后采集：{format_datetime(latest, self.config.timezone)}",
                f"时区：{self.config.timezone_name}",
            ]
        )

    def _history_text(self) -> str:
        servers = self.storage.latest_servers(self.config.server_ids, self.config.timezone)
        names = {int(server["akileId"]): server for server in servers}
        lines = ["最近 24 小时流量"]
        for akile_id in self.config.server_ids:
            hourly = self.storage.history(akile_id, 24, self.config.timezone)
            total_in = sum(item["in"] for item in hourly)
            total_out = sum(item["out"] for item in hourly)
            total = total_in + total_out
            peak = max(hourly, key=lambda item: item["in"] + item["out"], default={"h": "-", "in": 0, "out": 0})
            server = names.get(akile_id)
            title = f"{server['flag']} {server['name']}" if server else f"VPS {akile_id}"
            lines.extend(
                [
                    "",
                    title,
                    f"入站：{total_in:.2f} GiB",
                    f"出站：{total_out:.2f} GiB",
                    f"合计：{total:.2f} GiB",
                    f"峰值小时：{peak['h']} 点，{peak['in'] + peak['out']:.2f} GiB",
                ]
            )
        return "\n".join(lines)

    async def _collect(self, chat_id: str) -> None:
        await self._send(chat_id, "开始采集 Akile 数据...")
        result = await self.service.collect()
        collected_at = datetime.fromtimestamp(int(result["collected_at"]), self.config.timezone).strftime("%Y-%m-%d %H:%M:%S")
        await self._send(chat_id, f"采集完成：{result['servers']} 台 VPS\n时间：{collected_at}")

    async def _report(self, chat_id: str) -> None:
        await self._send(chat_id, "正在生成日报截图...")
        result = await self.service.send_report(chat_ids=[chat_id])
        if not result.get("ok"):
            await self._send(chat_id, f"截图已生成，但发送图片失败：{result.get('path')}")
