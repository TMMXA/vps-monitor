from __future__ import annotations

from pathlib import Path
from collections.abc import Sequence

import httpx

from .config import AppConfig


class TelegramNotifier:
    def __init__(self, config: AppConfig):
        self.config = config

    def _chat_ids(self, chat_ids: Sequence[str] | None = None) -> list[str]:
        return [str(chat_id) for chat_id in (chat_ids or self.config.telegram_chat_ids)]

    async def send_message(self, text: str, chat_ids: Sequence[str] | None = None) -> bool:
        if not self.config.has_telegram_credentials:
            print("Telegram is not configured; skipping message")
            return False
        target_chat_ids = self._chat_ids(chat_ids)
        if not target_chat_ids:
            return False
        ok = True
        async with httpx.AsyncClient(timeout=30, proxy=self.config.telegram_proxy_url or None) as client:
            for chat_id in target_chat_ids:
                response = await client.post(
                    f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage",
                    json={"chat_id": chat_id, "text": text},
                )
                if response.status_code >= 400:
                    ok = False
                    print(f"Telegram sendMessage failed for chat {chat_id}: HTTP {response.status_code}")
        return ok

    async def send_photo(
        self,
        image_path: Path,
        caption: str | None = None,
        chat_ids: Sequence[str] | None = None,
    ) -> bool:
        if not self.config.has_telegram_credentials:
            print("Telegram is not configured; skipping photo")
            return False
        target_chat_ids = self._chat_ids(chat_ids)
        if not target_chat_ids:
            return False
        ok = True
        async with httpx.AsyncClient(timeout=60, proxy=self.config.telegram_proxy_url or None) as client:
            for chat_id in target_chat_ids:
                with image_path.open("rb") as handle:
                    response = await client.post(
                        f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendPhoto",
                        data={"chat_id": chat_id, "caption": caption or ""},
                        files={"photo": (image_path.name, handle, "image/png")},
                    )
                if response.status_code >= 400:
                    ok = False
                    print(f"Telegram sendPhoto failed for chat {chat_id}: HTTP {response.status_code}")
        return ok
