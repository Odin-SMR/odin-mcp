"""Anonymous HTTPS transport with explicit origin, transfer and time budgets."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import re
import time
from typing import Any
from urllib.parse import unquote, urlsplit

import httpx

from odin_mcp.config import PUBLIC_ORIGIN, SETTINGS, Settings


class PublicDataError(ValueError):
    """A public request, catalog or resource limit prevented a complete result."""


def validate_public_url(url: str, *, kind: str) -> str:
    if not isinstance(url, str) or len(url) > 4096 or any(ord(c) < 33 or ord(c) == 127 for c in url):
        raise PublicDataError("Expected a canonical public Odin HTTPS URL")
    try:
        parsed = urlsplit(url)
    except ValueError as exc:
        raise PublicDataError("Invalid public Odin URL") from exc
    if parsed.scheme != "https" or parsed.netloc != "odin-smr.org" or parsed.query or parsed.fragment:
        raise PublicDataError("Only https://odin-smr.org URLs without credentials, query or fragment are accepted")
    path = parsed.path
    if not path.startswith("/") or "//" in path or "\\" in path:
        raise PublicDataError("Invalid public Odin URL path")
    inspected = path
    for _ in range(5):
        if any(part in (".", "..") for part in inspected.split("/")) or "\\" in inspected or any(ord(c) < 32 or ord(c) == 127 for c in inspected):
            raise PublicDataError("Unsafe public URL path")
        if re.search(r"%(?![0-9a-fA-F]{2})", inspected):
            raise PublicDataError("Malformed percent escape in public URL")
        decoded = unquote(inspected)
        if decoded.count("/") != path.count("/"):
            raise PublicDataError("Encoded path separators are not accepted")
        if decoded == inspected:
            break
        inspected = decoded
    else:
        raise PublicDataError("Excessively encoded public URL")
    if kind == "metadata":
        allowed = path in ("/parquet/archive/index.json", "/parquet/catalog.json") or bool(
            re.fullmatch(r"/parquet/archive/[A-Za-z0-9._-]+/g-[a-zA-Z0-9_-]+\.json", path)
        )
    elif kind == "parquet":
        allowed = (path.startswith("/l2/") or path.startswith("/parquet/releases/")) and path.endswith(".parquet")
    else:
        raise PublicDataError("Unknown public resource type")
    if not allowed:
        raise PublicDataError("URL is outside the supported public Odin catalog/data paths")
    return url


def absolute_metadata_url(path: str) -> str:
    return validate_public_url(PUBLIC_ORIGIN + path if path.startswith("/") else path, kind="metadata")


@dataclass
class Budget:
    settings: Settings = SETTINGS
    started: float = field(default_factory=time.monotonic)
    requests: int = 0
    metadata_bytes: int = 0
    download_bytes: int = 0
    decoded_bytes: int = 0
    output_arrow_bytes: int = 0

    def check_time(self) -> None:
        if time.monotonic() - self.started > self.settings.operation_timeout_seconds:
            raise PublicDataError("Operation deadline exceeded; narrow the selection and retry")

    def begin_request(self) -> None:
        self.check_time()
        if self.requests >= self.settings.max_http_requests:
            raise PublicDataError("HTTP request budget exceeded; narrow the product/mode selection")
        self.requests += 1

    def consume(self, purpose: str, size: int) -> None:
        if purpose == "metadata":
            self.metadata_bytes += size
            used, maximum = self.metadata_bytes, self.settings.max_metadata_bytes
        else:
            self.download_bytes += size
            used, maximum = self.download_bytes, self.settings.max_download_bytes
        if used > maximum:
            raise PublicDataError(f"{purpose.capitalize()} byte budget exceeded; narrow the selection")
        self.check_time()

    def reserve_decoded(self, size: int) -> None:
        if size < 0 or self.decoded_bytes + size > self.settings.max_decoded_bytes:
            raise PublicDataError("Selected Parquet row-group decode budget exceeded; select fewer columns or use a local analysis script")
        self.decoded_bytes += size
        self.check_time()

    def check_output(self, data: Any) -> None:
        self.check_time()
        encoded = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        if len(encoded) > self.settings.max_output_bytes:
            raise PublicDataError("JSON output budget exceeded, including nested arrays; request fewer rows/columns")

    def receipt(self) -> dict[str, Any]:
        return {"http_requests": self.requests, "metadata_bytes": self.metadata_bytes,
                "download_bytes": self.download_bytes, "selected_row_groups_decoded_bytes": self.decoded_bytes,
                "output_limit_scope": "Compact logical result JSON; MCP framing and duplicate text/structured representations add wire bytes",
                "limits": {name: getattr(self.settings, name) for name in (
                    "max_metadata_response_bytes", "max_metadata_bytes", "max_file_bytes",
                    "max_download_bytes", "max_decoded_bytes", "max_output_bytes", "max_http_requests",
                    "operation_timeout_seconds")},
                "deadline_scope": "Checked between requests, streamed chunks and decodes; not a hard interruption of native Arrow decoding"}


def _client() -> httpx.Client:
    # Fresh clients cannot forward response cookies to subsequent requests.
    return httpx.Client(trust_env=False, follow_redirects=False, auth=None,
                        timeout=httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0),
                        headers={"Accept-Encoding": "identity", "User-Agent": "odin-mcp-public-client"})


def fetch_bytes(url: str, budget: Budget, *, purpose: str, expected_size: int | None = None,
                expected_etag: str | None = None) -> tuple[bytes, dict[str, Any]]:
    validate_public_url(url, kind="metadata" if purpose == "metadata" else "parquet")
    maximum = budget.settings.max_metadata_response_bytes if purpose == "metadata" else budget.settings.max_file_bytes
    remaining = (budget.settings.max_metadata_bytes - budget.metadata_bytes if purpose == "metadata"
                 else budget.settings.max_download_bytes - budget.download_bytes)
    if expected_size is not None and (expected_size > maximum or expected_size > remaining):
        raise PublicDataError("Published file exceeds this call's download budget; use the listed public URL in a bounded local analysis script")
    headers = {}
    if expected_etag is not None:
        if not re.fullmatch(r"[A-Za-z0-9_.:+/=-]{1,200}", expected_etag):
            raise PublicDataError("Invalid catalog ETag")
        headers["If-Match"] = f'"{expected_etag}"'
    budget.begin_request()
    try:
        with _client() as client:
            with client.stream("GET", url, headers=headers) as response:
                if response.status_code != 200:
                    raise PublicDataError(f"Public HTTPS request returned HTTP {response.status_code}; redirects are not followed")
                if response.headers.get("Content-Encoding", "identity").lower() not in ("", "identity"):
                    raise PublicDataError("Encoded HTTP responses are refused to keep transfer budgets explicit")
                length = response.headers.get("Content-Length")
                if length is not None:
                    if not length.isdigit():
                        raise PublicDataError("Invalid HTTP Content-Length")
                    length = int(length)
                    if length > maximum or length > remaining:
                        raise PublicDataError("HTTP response exceeds the byte budget")
                    if expected_size is not None and length != expected_size:
                        raise PublicDataError("Public file size differs from the catalog; refresh discovery")
                etag = response.headers.get("ETag")
                if expected_etag is not None and etag != f'"{expected_etag}"':
                    raise PublicDataError("HTTP ETag differs from or is missing for the catalog entry; refresh discovery")
                body = bytearray()
                for chunk in response.iter_raw():
                    budget.consume(purpose, len(chunk))
                    if len(body) + len(chunk) > maximum:
                        raise PublicDataError("Streamed HTTP response exceeds the byte budget")
                    body.extend(chunk)
                if length is not None and len(body) != length:
                    raise PublicDataError("Incomplete HTTP response")
                if expected_size is not None and len(body) != expected_size:
                    raise PublicDataError("Downloaded file size differs from the catalog")
                budget.check_time()
                return bytes(body), {"url": url, "size_bytes": len(body), "etag": etag,
                                     "last_modified": response.headers.get("Last-Modified"),
                                     "sha256": hashlib.sha256(body).hexdigest()}
    except httpx.TimeoutException as exc:
        raise PublicDataError("Public HTTPS request timed out; retry a narrower selection") from exc
    except httpx.HTTPError as exc:
        raise PublicDataError("Public HTTPS transport failed; no complete result was produced") from exc


def fetch_json(url: str, budget: Budget) -> tuple[dict[str, Any], str]:
    body, receipt = fetch_bytes(url, budget, purpose="metadata")
    try:
        def reject_constant(value: str) -> None:
            raise ValueError("Non-finite JSON metadata")
        def finite_float(value: str) -> float:
            parsed = float(value)
            if not math.isfinite(parsed):
                raise ValueError("Non-finite JSON metadata")
            return parsed
        document = json.loads(body, parse_constant=reject_constant, parse_float=finite_float)
    except (ValueError, UnicodeDecodeError, RecursionError) as exc:
        raise PublicDataError("Public catalog did not contain valid finite JSON") from exc
    if not isinstance(document, dict) or type(document.get("schema_version")) is not int or document["schema_version"] != 1:
        raise PublicDataError("Unsupported public catalog schema")
    return document, receipt["sha256"]
