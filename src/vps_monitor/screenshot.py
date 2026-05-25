from __future__ import annotations

import os
import time
from pathlib import Path

from playwright.async_api import async_playwright

from .config import AppConfig


async def capture_report(config: AppConfig) -> Path:
    config.report_dir.mkdir(parents=True, exist_ok=True)
    output = config.report_dir / f"report-{int(time.time())}.png"
    url = f"http://127.0.0.1:{config.web_port}/?screenshot=1"

    async with async_playwright() as playwright:
        launch_options = {"args": ["--no-sandbox"]}
        chromium_path = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
        if chromium_path:
            launch_options["executable_path"] = chromium_path
        browser = await playwright.chromium.launch(**launch_options)
        page = await browser.new_page(viewport={"width": 1200, "height": 1800}, device_scale_factor=1)
        await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        await page.wait_for_selector(".report.ready", timeout=30_000)
        await page.wait_for_timeout(1000)
        report = page.locator(".report")
        await report.screenshot(path=str(output))
        await browser.close()

    return output
