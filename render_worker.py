"""Playwright worker that opens the autopilot URL in a real Chromium
under Xvfb and captures the MediaRecorder download.

Invoked from app.py's /record endpoint when CelebiPlug runs in Docker
(VPS) mode. The local Mac/PC flow never touches this file.

Usage:
    xvfb-run -a python3 render_worker.py <autopilot_url> <output_path>
"""

import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright


CHROMIUM_FLAGS = [
    "--use-gl=swiftshader",
    "--enable-webgl",
    "--ignore-gpu-blocklist",
    "--enable-features=Vulkan",
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--autoplay-policy=no-user-gesture-required",
]

RECORD_TIMEOUT_MS = 180_000
DOWNLOAD_EXTENSIONS = {".mp4", ".webm"}


def resolve_output_path(output_path: str, suggested_filename: str) -> Path:
    path = Path(output_path)
    if path.suffix:
        return path

    suffix = Path(suggested_filename or "").suffix.lower()
    if suffix not in DOWNLOAD_EXTENSIONS:
        suffix = ".webm"
    return path.with_suffix(suffix)


async def render(autopilot_url: str, output_path: str) -> int:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=CHROMIUM_FLAGS)
        try:
            context = await browser.new_context(
                accept_downloads=True,
                viewport={"width": 1920, "height": 1080},
            )
            page = await context.new_page()

            page.on("console", lambda msg: print(f"[page:{msg.type}] {msg.text}", flush=True))
            page.on("pageerror", lambda err: print(f"[page:error] {err}", flush=True))

            async with page.expect_download(timeout=RECORD_TIMEOUT_MS) as dl_info:
                await page.goto(autopilot_url, wait_until="load")
            download = await dl_info.value
            final_output_path = resolve_output_path(output_path, download.suggested_filename)
            await download.save_as(str(final_output_path))
            print(f"[worker] saved {final_output_path}", flush=True)
            return 0
        finally:
            await browser.close()


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: render_worker.py <autopilot_url> <output_path>", file=sys.stderr)
        return 2
    return asyncio.run(render(sys.argv[1], sys.argv[2]))


if __name__ == "__main__":
    sys.exit(main())
