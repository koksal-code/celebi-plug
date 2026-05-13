"""Tiny urllib wrapper. No requests dep — keeps install minimal."""

from __future__ import annotations

import gzip
import io
import json as _json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

USER_AGENT = "CelebiPlug/1.0 (+https://github.com/koksal-code/celebi-plug)"
DEFAULT_TIMEOUT = 8.0


class HttpError(RuntimeError):
    """Raised on HTTP transport / status errors."""

    def __init__(self, status: int, message: str):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status


def _open(url: str, *, params: dict | None, headers: dict | None, timeout: float):
    if params:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}{urllib.parse.urlencode(params)}"
    req_headers = {
        "User-Agent": USER_AGENT,
        "Accept-Encoding": "gzip",
    }
    if headers:
        req_headers.update(headers)
    request = urllib.request.Request(url, headers=req_headers)
    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        raise HttpError(exc.code, exc.reason or "http error") from exc
    except urllib.error.URLError as exc:
        raise HttpError(0, str(exc.reason)) from exc
    except TimeoutError as exc:
        raise HttpError(0, f"timeout after {timeout}s") from exc


def _read(response) -> bytes:
    raw = response.read()
    if response.headers.get("Content-Encoding") == "gzip":
        raw = gzip.decompress(raw)
    return raw


def get_json(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Any:
    with _open(url, params=params, headers=headers, timeout=timeout) as response:
        data = _read(response)
    return _json.loads(data.decode("utf-8"))


def get_text(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    with _open(url, params=params, headers=headers, timeout=timeout) as response:
        data = _read(response)
    return data.decode("utf-8", errors="replace")


def get_bytes(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> bytes:
    with _open(url, params=params, headers=headers, timeout=timeout) as response:
        return _read(response)


def stream_to(path, url: str, *, timeout: float = 30.0) -> None:
    with _open(url, params=None, headers=None, timeout=timeout) as response:
        with open(path, "wb") as fh:
            buf = io.BytesIO(_read(response))
            fh.write(buf.getvalue())
