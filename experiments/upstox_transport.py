"""Hardened HTTP transport for the isolated Upstox read-only experiment.

This module knows nothing about orders, portfolios, forecasts, databases or 5DR.
It adapts urllib Request objects created by the existing read-only client to curl
because Upstox/Cloudflare currently rejects Python urllib's browser signature.
"""
import io
import subprocess
from urllib.error import HTTPError, URLError


_STATUS_MARKER = b"\n__5DR_HTTP_STATUS__="


class CurlResponse:
    def __init__(self, body: bytes, status: int):
        self._body = body
        self.status = status

    def read(self, size=-1):
        return self._body if size is None or size < 0 else self._body[:size]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class CurlOpener:
    """GET-only, no-redirect curl adapter.

    Authorization headers are sent to curl over stdin using ``--header @-`` so
    credentials never appear in process arguments. stdout is captured in memory;
    stderr and response bodies are never printed by this adapter.
    """

    def __init__(self, runner=subprocess.run, max_bytes=8_000_001):
        self._runner = runner
        self._max_bytes = int(max_bytes)
        if self._max_bytes <= 0:
            raise ValueError("max_bytes must be positive")

    def open(self, request, timeout=20):
        if request.get_method() != "GET":
            raise URLError("non-GET transport request refused")

        header_text = "".join(
            f"{name}: {value}\n" for name, value in request.header_items()
        ) + "\n"
        command = [
            "curl",
            "--silent",
            "--show-error",
            "--max-time",
            str(int(timeout)),
            "--max-filesize",
            str(self._max_bytes),
            "--request",
            "GET",
            "--header",
            "@-",
            "--write-out",
            "\\n__5DR_HTTP_STATUS__=%{http_code}",
            request.full_url,
        ]
        try:
            result = self._runner(
                command,
                input=header_text.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=timeout + 5,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise URLError("curl transport failed") from error

        if result.returncode != 0:
            raise URLError("curl transport failed")
        if _STATUS_MARKER not in result.stdout:
            raise URLError("curl status marker missing")

        body, status_raw = result.stdout.rsplit(_STATUS_MARKER, 1)
        if len(body) > self._max_bytes:
            raise URLError("curl response exceeds size limit")
        try:
            status = int(status_raw.strip())
        except ValueError as error:
            raise URLError("curl status invalid") from error

        if status < 200 or status >= 300:
            raise HTTPError(
                request.full_url,
                status,
                "HTTP error",
                None,
                io.BytesIO(body),
            )
        return CurlResponse(body, status)
