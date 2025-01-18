# cache.py
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

import aiofiles

CACHE_DIR = Path(".cache/pkgs")

class PackageCache:
    def __init__(self, cache_dir: str | Path = CACHE_DIR, ttl_hours: int = 6):
        self.cache_dir = Path(cache_dir)
        self.ttl = timedelta(hours=ttl_hours)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def get_or_fetch(self, pkg_name: str, fetch_func) -> Dict[str, Any]:
        cache_file = self.cache_dir / f"{pkg_name}.json"
        
        if await self._is_cache_valid(cache_file):
            async with aiofiles.open(cache_file, 'r') as f:
                return json.loads(await f.read())
        
        data = await fetch_func(pkg_name)
        await self._save_cache(cache_file, data)
        return data

    async def _is_cache_valid(self, cache_file: Path) -> bool:
        if not cache_file.exists():
            return False
        
        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        return datetime.now() - mtime < self.ttl

    async def _save_cache(self, cache_file: Path, data: Dict[str, Any]):
        async with aiofiles.open(cache_file, 'w') as f:
            await f.write(json.dumps(data))


