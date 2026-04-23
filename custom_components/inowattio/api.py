"""HTTP client for Nemesis local API."""

from __future__ import annotations

from ipaddress import IPv6Address
from ipaddress import ip_address
from typing import Any

from aiohttp import ClientError
from aiohttp import ClientSession
from aiohttp import ClientTimeout

from .const import ENDPOINT_DATA
from .const import ENDPOINT_STATUS


class NemesisApiError(Exception):
    """Raised when the device API returns an error."""


def http_base_url(host: str, port: int) -> str:
    try:
        if isinstance(ip_address(host), IPv6Address):
            return f"http://[{host}]:{port}"
    except ValueError:
        pass
    return f"http://{host}:{port}"


class NemesisApi:
    """Thin async client for /status and /data."""

    def __init__(self, session: ClientSession, host: str, port: int) -> None:
        self._session = session
        self._base = http_base_url(host, port)
        self._timeout = ClientTimeout(total=15)

    async def get_status(self) -> dict[str, Any]:
        return await self._get_json(ENDPOINT_STATUS)

    async def get_data(self) -> dict[str, Any]:
        return await self._get_json(ENDPOINT_DATA)

    async def _get_json(self, path: str) -> dict[str, Any]:
        url = f"{self._base}{path}"
        try:
            async with self._session.get(url, timeout=self._timeout) as resp:
                if resp.status != 200:
                    snippet = (await resp.text())[:200]
                    raise NemesisApiError(f"HTTP {resp.status} for {path}: {snippet}")
                data = await resp.json()
        except ClientError as err:
            raise NemesisApiError(f"Request failed for {path}: {err}") from err
        except (TypeError, ValueError) as err:
            raise NemesisApiError(f"Invalid JSON from {path}: {err}") from err
        if not isinstance(data, dict):
            raise NemesisApiError(f"Expected JSON object from {path}")
        return data
