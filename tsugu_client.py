import asyncio
import time
from typing import Any

import aiohttp


class TsuguClientError(Exception):
    pass


class TsuguClient:
    def __init__(
        self,
        backend_url: str,
        data_backend_url: str | None = None,
        *,
        timeout: int = 20,
        proxy: str | None = None,
        retries: int = 2,
    ):
        self.backend_url = backend_url.rstrip("/")
        self.data_backend_url = (data_backend_url or backend_url).rstrip("/")
        self.timeout = max(1, int(timeout))
        self.proxy = proxy or None
        self.retries = max(0, int(retries))
        self.session: aiohttp.ClientSession | None = None

    async def open(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        data: dict[str, Any] | None = None,
        use_data_backend: bool = False,
    ) -> Any:
        await self.open()
        assert self.session is not None
        base = self.data_backend_url if use_data_backend else self.backend_url
        url = f"{base}{path}"
        last_error: Exception | None = None

        for attempt in range(self.retries + 1):
            try:
                async with self.session.request(
                    method,
                    url,
                    json=data,
                    proxy=self.proxy,
                ) as response:
                    try:
                        payload = await response.json(content_type=None)
                    except Exception:
                        payload = await response.text()

                    if 200 <= response.status < 300:
                        return payload

                    if isinstance(payload, dict) and payload.get("data"):
                        raise TsuguClientError(str(payload["data"]))
                    raise TsuguClientError(f"HTTP {response.status}: {payload}")
            except Exception as exc:
                last_error = exc
                if attempt < self.retries:
                    await asyncio.sleep(1)

        raise TsuguClientError(f"后端请求失败: {last_error}")

    async def post(
        self,
        path: str,
        data: dict[str, Any],
        *,
        use_data_backend: bool = False,
    ) -> Any:
        return await self._request(
            "POST", path, data=data, use_data_backend=use_data_backend
        )

    async def get(self, path: str, *, use_data_backend: bool = False) -> Any:
        return await self._request("GET", path, use_data_backend=use_data_backend)


def now_ms() -> int:
    return int(time.time() * 1000)
