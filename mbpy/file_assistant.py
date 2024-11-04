from functools import partial
import logging
import os
import hashlib
import asyncio
from pathlib import Path
import pyclbr
import pydoc
from aiofiles.os import scandir as async_scandir
from typing import Dict, Optional
from contextlib import chdir
from pickle import dumps as pdumps, loads as ploads
from atexit import register
from uvloop import install
import aiofiles

install()


def dumps(summary_cache, path="."):
    if Path(path).is_dir():
        path = Path(path) / ".summary_cache"
    Path(path).resolve().expanduser().write_bytes(pdumps(summary_cache))


def loads(path):
    if Path(path).exists():
        if Path(path).is_dir():
            path = Path(path) / ".summary_cache"
        return ploads(Path(path).resolve().expanduser().read_bytes())
    return {}


GITIGNORE_CONTENT = set()


def read_gitignore():
    if Path(".gitignore").exists():
        global GITIGNORE_CONTENT
        GITIGNORE_CONTENT |= set(Path(".gitignore").read_text().splitlines())
    return GITIGNORE_CONTENT


class HierarchicalLanguageAgent:
    # Class-level cache and lock
    summary_cache: Dict[str, str] = loads(".summary_cache")
    cache_lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(100)  # Limits concurrency

    def __init__(
        self, path: str | None = None, name: str | None = None, model_src: str | None = None, api_key: str | None = None
    ):
        self.path = Path(path).resolve() if path else Path.cwd().resolve().expanduser()
        self.name = name if name else self.path.name
        self.model_src = model_src
        self.api_key = api_key
        self.children: Dict[str, HierarchicalLanguageAgent | None] = {}
        self.curr_dir_hash = None
        register(partial(dumps, self.summary_cache))

    async def _discover_children(self):
        """Discover child directories that are valid packages and contain .md or .py files."""
        for entry in await async_scandir(self.path):
            if entry.is_dir() and not entry.name.startswith("."):
                init_file = Path(entry.path) / "__init__.py"
                if init_file.exists():
                    has_md_or_py = False
                    for sub_entry in await async_scandir(entry.path):
                        if sub_entry.is_file() and (sub_entry.name.endswith(".md") or sub_entry.name.endswith(".py")):
                            has_md_or_py = True
                            break
                    if has_md_or_py:
                        self.children[entry.name] = None  # Placeholder for lazy loading

    async def _create_directory_hash(self) -> str:
        """Create a unique hash for the directory based on .md and .py files."""
        hash_md5 = hashlib.md5()
        for entry in await async_scandir(self.path):
            if entry.name.startswith(".") or entry.name in read_gitignore():
                continue
            if entry.is_file() and (entry.name.endswith(".md") or entry.name.endswith(".py")):
                hash_md5.update(entry.name.encode("utf-8"))
                stat = await asyncio.to_thread(entry.stat)
                hash_md5.update(str(stat.st_mtime).encode("utf-8"))
                hash_md5.update(str(stat.st_size).encode("utf-8"))
            elif entry.is_dir():
                entry = Path(entry) / ".md5"
                if entry.exists():
                    hash_md5.update(entry.read_bytes())
                else:
                    await self._load_child_agent(entry.name)._create_directory_hash()
                hash_md5.update((entry / ".md5").read_bytes())

        return hash_md5.hexdigest()

    async def update_directory_hash(self) -> bool:
        """Update the directory hash and children hashes."""
        if not (Path(self.path).parent / ".md5").exists():
            (Path(self.path).parent / ".md5").write_bytes(await self._create_directory_hash())
        self.curr_dir_hash_file = Path(self.path).parent / ".md5"
        new_hash = await self._create_directory_hash()
        if new_hash != self.curr_dir_hash_file.read_bytes():
            self.curr_dir_hash_file.write_bytes(new_hash.encode("utf-8"))
            self.curr_dir_hash = new_hash
            return False
        return True

    async def _load_child_agent(self, child_name: str) -> "HierarchicalLanguageAgent":
        """Lazy load a child agent representing a subdirectory."""
        if self.children.get(child_name) is None:
            child_path = self.path / child_name
            self.children[child_name] = HierarchicalLanguageAgent(
                model_src=self.model_src, api_key=self.api_key, path=child_path, name=child_name
            )
        return self.children[child_name]

    # async def _load_child_agent(self, name):
    #     # Placeholder for loading child agent
    #     return type(self)(Path(self.path) / name)

    async def _create_directory_hash(self) -> str:
        """Create a unique hash for the directory based on .md and .py files."""
        hash_md5 = hashlib.md5()
        for entry in await async_scandir(self.path):
            if entry.name.startswith(".") or entry.name in read_gitignore():
                continue
            if entry.is_file() and (entry.name.endswith(".md") or entry.name.endswith(".py")):
                hash_md5.update(entry.name.encode("utf-8"))
                stat = await asyncio.to_thread(entry.stat)
                hash_md5.update(str(stat.st_mtime).encode("utf-8"))
                hash_md5.update(str(stat.st_size).encode("utf-8"))
            elif entry.is_dir():
                child_agent = await self._load_child_agent(entry.name)
                child_hash = await child_agent._create_directory_hash()
                hash_md5.update(child_hash.encode("utf-8"))

        # Write the hash to the .md5 file
        md5_file = Path(self.path) / ".md5"
        async with aiofiles.open(md5_file, "w") as f:
            await f.write(hash_md5.hexdigest())

        return hash_md5.hexdigest()

    async def generate_summary(self, cache=True) -> str:
        """Generate a nested summary of the directory."""
        summary = {
            self.name: {
                "brief": f"Summary for {self.name}",
                "details": await self._generate_leaf_summary(),
                "children": {},
            }
        }

        summaries = await self.request_summary_from_children(cache=cache)
        summary[self.name]["children"].update(summaries)

        # Cache the summary
        async with self.cache_lock:
            self.summary_cache[self.curr_dir_hash] = summary

        return summary

    async def _generate_leaf_summary(self) -> str:
        """Generate a summary for leaf nodes using pydoc."""
        with chdir(self.path):
            try:
                mod = pydoc.safeimport(self.name)
                if mod is None:
                    return f"Failed to import {self.name}"
                loader = getattr(mod, '__loader__', None)
                if loader and hasattr(loader, 'get_filename'):
                    module_info = pyclbr.readmodule(self.name, [self.path])
                    return module_info
                else:
                    logging.error(f"Module loader for {self.name} does not support get_filename")
                    return f"Module loader for {self.name} does not support get_filename"
            except Exception as e:
                logging.error(f"Error processing module {self.name}: {e}")
                return f"Failed to process module {self.name}: {e}"

    async def get_summary(self, cache=True) -> str:
        """Get a summary for the directory and its children using a shared cache."""
        new_changes = await self.update_directory_hash()
        if not new_changes:
            logging.info("No changes detected")
        async with self.cache_lock:
            cached_summary = self.summary_cache.get(self.curr_dir_hash)
            if cached_summary and cache:
                logging.info("Returning cached summary")
                return cached_summary
        logging.info("Generating new summary")
        return await self.generate_summary(cache=cache)

    # async def update_directory_hash(self) -> str:
    #     """Update the tory hash and write it to the parent directory."""
    #     hash_value = await self._create_directory_hash()
    #     (Path(self.path).parent / ".md5").write_bytes(hash_value.encode("utf-8"))
    #     return hash_value
    async def request_summary_from_children(self, cache) -> Dict[str, str]:
        """Request summaries from each child agent asynchronously."""
        await self._discover_children()
        summaries = {}

        async def get_child_summary(child_name: str):
            child_agent = await self._load_child_agent(child_name)
            try:
                return child_name, await child_agent.get_summary(cache=cache)
            except Exception as e:
                logging.error(f"Error generating summary for {child_name}: {e}")
                return child_name, f"Failed to generate summary: {e}"

        # Collect child summaries concurrently
        tasks = [get_child_summary(name) for name in self.children.keys()]
        results = await asyncio.gather(*tasks)
        summaries.update(results)

        return summaries


if __name__ == "__main__":
    agent = HierarchicalLanguageAgent(model_src="gpt-2", path=".")
    import logging

    logging.basicConfig(level=logging.INFO)
    summary = asyncio.run(agent.get_summary(cache=True))
    print(summary)
