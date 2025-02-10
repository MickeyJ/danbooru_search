import aiohttp
import ssl
import asyncio
from typing import Dict, Any, List


class DanbooruAPI:
    BASE_URL = "https://danbooru.donmai.us"

    def __init__(self):
        self.ssl_context = ssl.create_default_context()
        self.timeout = aiohttp.ClientTimeout(total=60)

    async def get_tags_page(self, page: int, limit: int = 1000) -> List[Dict[str, Any]]:
        """Fetch a page of tags from the API"""
        params = {
            "page": page,
            "limit": limit,
            "search[order]": "id_asc",
        }

        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=self.ssl_context), timeout=self.timeout
        ) as session:
            async with session.get(
                f"{self.BASE_URL}/tags.json", params=params, timeout=30
            ) as response:
                if response.status == 410:
                    return None  # End of tags
                response.raise_for_status()
                return await response.json()
