"""Synchronizes requirements and hatch pyproject."""

import logging
import re
import sys
from time import time
import traceback
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List
from typing_extensions import TypedDict
from mbpy.import_utils import smart_import


INFO_KEYS = [
    "author",
    "author_email",
    "bugtrack_url",
    "classifiers",
    "description",
    "description_content_type",
    "docs_url",
    "download_url",
    "downloads",
    "dynamic",
    "home_page",
    "keywords",
    "license",
    "maintainer",
    "maintainer_email",
    "name",
    "package_url",
    "platform",
    "project_url",
    "project_urls",
    "provides_extra",
    "release_url",
    "requires_dist",
    "requires_python",
    "summary",
    "version",
    "yanked",
    "yanked_reason",
]
ADDITONAL_KEYS = ["last_serial", "releases", "urls", "vulnerabilities"]
if TYPE_CHECKING:
    from asyncio import Task
    from mbpy.pkg.dependency import PyPackageInfo as PackageInfo
    from typing import Dict, AsyncGenerator
    import playwright.async_api as pw
    from aiohttp import ClientSession as Client
    from playwright.async_api import Response as PWResponse
    from playwright.async_api import async_playwright
    from bs4 import BeautifulSoup
    from mrender.md import Markdown
    from mrender.web2md import html_to_markdown_with_depth
else:
    try:
        PWResponse = smart_import("playwright.async_api.Response","type_safe_lazy")
    except Exception as e:
        from mbpy.helpers._display import isverbose
        if isverbose():
            traceback.print_exc()
        PWResponse = object
    ThreadPoolExecutor = smart_import("concurrent.futures.ThreadPoolExecutor","type_safe_lazy")
    Client = smart_import("aiohttp.ClientSession","type_safe_lazy")

class Response(PWResponse):
    _links: List[str] = []
    _status: int = 0
    _text: str = ""
    _task: "Task[str]"
    def __new__(cls, text="", links=[],response=None):
        import asyncio
        create_task = asyncio.create_task
        cls = super().__new__(cls)
        cls.__init__(text=text,links=links,task_factory=create_task,response=response)
        return cls


    def __init__(self, text=None,links=[],task_factory=None,response: "PWResponse | None" =None):
        if text:
            self._text = text
        if links:
            self._links = links
        if response:
            self._status = response.status
            create_task = smart_import("asyncio.create_task")
            task_factory = task_factory or create_task
            self._task = create_task(super().text())

            super().__init__(response)
            def set_text(fut: "Task[str]"):
                self._text = fut.result()
            self._task.add_done_callback(set_text)
        else:
            self._status = 0

    @property
    def links(self):
        return self._links
    @property
    def ok(self):
        return self.status == 200

    @property
    def status(self):
        return self._status
    @property
    def waited(self):
        last_coro = self._task.get_coro()
        cr_frame = last_coro.cr_frame if last_coro else None
        sttime = cr_frame.f_lasti if cr_frame else None

        return (time() - sttime) if sttime else -1
    @property
    def text(self):
        self._task = getattr(self,"_task",None)
        if self._text:
            return self._text
        while not (not self._task or self._task.done()) and self.waited < 5:
            pass
        return self._text
_client = None
def get_client():
    global _client
    if not _client:
        _client = Client()
    return _client


_browser = None
_context = None

async def get_browser(url="", headers=None):
    global _browser, _context
    if not _browser:
        if TYPE_CHECKING:
            import playwright.async_api as pw
        else:
            pw = smart_import("playwright.async_api")
            
        # Configure browser based on URL
        config = {
            "headless": True,
            "args": ["--no-sandbox", "--disable-setuid-sandbox"]
        }
        
        # Add specific configuration for different sites
        if "pypi.org" in url:
            config["bypassCSP"] = True
            config["javaScriptEnabled"] = False
        
        async_playwright = pw.async_playwright
        p = await async_playwright().start()
        _browser = await p.chromium.launch(**config)
        
        # Set context with appropriate headers
        ctx_config = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "extra_http_headers": headers or {"Accept-Language": "en-US,en;q=0.9"}
        }
        
        _context = await _browser.new_context(**ctx_config)
        
        # Route handlers for performance
        if "pypi" in url:
            await _context.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2}", lambda route: route.abort())
            
    return _context

async def browse_web(url, headers=None) -> "Response":
    """Browse web with improved HTML parsing and error handling."""
    try:
        context = await get_browser(url, headers)
        page = await context.new_page()
        
        try:
            # Configure timeout and navigation
            timeout = 5000  # 5 seconds
            response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            
            try:
                await page.wait_for_load_state("networkidle", timeout=timeout)
            except Exception as e:
                logging.debug(f"Networkidle timeout for {url}: {e}")
            
            content = await page.content()
            
            # Use BeautifulSoup for robust HTML parsing
            if not TYPE_CHECKING:
                BeautifulSoup = smart_import("bs4.BeautifulSoup")
            else:
                from bs4 import BeautifulSoup
                
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extract clean content and links
            parsed_content = str(soup)
            links = []
            
            for a in soup.find_all('a', href=True):
                href = a.get('href', '')
                if href.startswith('http'):
                    links.append(href)
                elif href.startswith('/') and not href.startswith('//'):
                    # Handle relative URLs
                    from urllib.parse import urljoin
                    links.append(urljoin(url, href))
            
            return Response(links=links, text=parsed_content)
            
        finally:
            await page.close()

    except Exception as e:
        logging.debug(f"Error browsing {url}: {e}")
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            traceback.print_exc()
        return Response("", [])

def save_results_to_file(results, filename="search_results.txt"):
    with open(filename, "w", encoding="utf-8") as f:
        for item in results:
            f.write(f"{item['title']} - {item['url']}\n")

async def browse(urls, timeout=25, interactive=False) -> "List[Dict[str, Markdown | str]]":
    urls = [urls] if isinstance(urls, str) else urls
  
  
    if not TYPE_CHECKING:
        BeautifulSoup = smart_import("bs4.BeautifulSoup") 
        debug = smart_import("mbpy.log.debug")
        log = smart_import("mbpy.log")
        html_to_markdown_with_depth = smart_import("mrender.web2md.html_to_markdown_with_depth")
        Markdown = smart_import("mrender.md.Markdown")
        HTMLParser = smart_import("lxml.etree.HTMLParser")
        HTML = smart_import("lxml.etree.HTML")
        Element = smart_import("lxml.html.Element")
        json = smart_import("json")
    else:
        from bs4 import BeautifulSoup
        from mbpy.log import debug, log
        from mrender.web2md import html_to_markdown_with_depth
        from mrender.md import Markdown
        from lxml.etree import HTMLParser, HTML,Element

    debug(f"browse function called with urls: {urls}, timeout: {timeout}, interactive: {interactive}")
    results = []
    for i, url in enumerate(urls):
        try:
            response = await browse_web(url)
            debug(f"Response status code: {response.status}")
            
            soup = BeautifulSoup(response.text, 'html.parser')

            title = soup.title.string if soup.title else "No title found"
            markdown_content = html_to_markdown_with_depth(soup, depth=3)            
            result = {
                'url': url,
                'title': title,
                'content': Markdown({e.name: e for e in soup.descendants}),
            }
            print(result["content"].data)
            results.append(result)

            
            log.info(f"Processed: {url}")
        except Exception as e:
            raise e
            log.error(f"Error fetching the webpage {url}: {str(e)}")
            error_message = f"Error fetching the webpage: {e.response.status_code if hasattr(e, 'response') else str(e)}"
            results.append({
                'url': url,
                'error': error_message,
            })
    return results

async def search_online(query: str, source: str = 'ddg', save_to_file: bool = False, attempt: int = 0) ->" List[Dict[str, str | Markdown]]":
    """Search online with proper fallback and recursion control."""
    
    # Prevent infinite recursion
    if attempt > 2:
        logging.warning(f"Max retry attempts reached for query: {query}")
        return []
        
    results = []
    base_url = {
        # 'google': f'https://www.google.com/search?q={query}',
        'github': f'https://github.com/search?q={query}&type=repositories',
        'ddg': f'https://duckduckgo.com/?q={query}'
    }.get(source, f'https://duckduckgo.com?q={query}')
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
    
        if not TYPE_CHECKING:
                BeautifulSoup = smart_import("bs4.BeautifulSoup")
        else:
            from bs4 import BeautifulSoup
        results = await browse(base_url, headers)
     
        
        if not results and source != 'ddg':
            logging.info(f"No results found with {source}, trying DuckDuckGo")
            return await search_online(query, 'ddg', save_to_file, attempt + 1)
            
        if save_to_file:
            save_results_to_file(results)
            
        return results
        
    except Exception as e:
        raise e
        logging.error(f"Error in search_online: {e}")
        if attempt < 2:
            # Try next source in priority order
            next_source = {'google': 'ddg', 'ddg': 'github', 'github': 'google'}[source]
            return await search_online(query, next_source, save_to_file, attempt + 1)
        return []
async def get_latest_version(package_name: str) -> str | None:
    """Get the latest version of the specified package from PyPI.

    Args:
        package_name (str): The name of the package to fetch the latest version for.

    Returns:
        Optional[str]: The latest version of the package, or None if not found or on error.
    """
    try:

        client = Client()

        response = await client.get(f"https://pypi.org/pypi/{package_name}/json")
        data = await response.json()
        return data["info"]["version"]
    except (KeyError, ValueError) as e:
        logging.exception(f"Error parsing response for {package_name}: {e}")
    except Exception as e:
        logging.exception(
            f"Unexpected error fetching latest version for {package_name}: {e}",
        )
    return ""


def extract_suggested_package(suggestion: str) -> str | None:
    """Extract package name from PyPI suggestion HTML."""
    import re

    # Match pattern: href="/search/\?q=package_name"
    pattern = r'href="/search/\?q=([^"]+)"'
    match = re.search(pattern, suggestion)

    if match:
        return match.group(1)

    # Fallback for plain text
    pattern = r'Did you mean [\'"]([^\'"]+)[\'"]'
    match = re.search(pattern, suggestion)

    return match.group(1) if match else None


async def get_package_names(query_key,client=None) -> list[str]:
    """Fetch package names from PyPI search results."""
    search_url = f"https://pypi.org/search/?q={query_key}"

    try:
        response = await browse_web(search_url)
    except Exception as e:
        from mbpy.helpers._display import isverbose
        if isverbose():
            traceback.print_exc()
        response = await get_package_info(query_key,client=client)
    logging.debug(f"Response status code: {getattr(response, 'status', response)}")

    page_content = getattr(response, "text", "")
    logging.debug(page_content)
    if 'Did you mean \'<a class="link" href="/search/?q=' in page_content:
        suggestion = extract_suggested_package(page_content)
        if suggestion:
            response = await client.get(
                f"https://pypi.org/search/?q={suggestion}",
            )
            page_content = response.text
    # Extract package names from search results
    start_token = '<a class="package-snippet"'  # noqa
    end_token = "</a>"  # noqa
    name_token = '<span class="package-snippet__name">'  # noqa

    package_names = []
    start = 0
    while True:
        start = page_content.find(start_token, start)
        if start == -1:
            break
        end = page_content.find(end_token, start)
        snippet = page_content[start:end]
        name_start = snippet.find(name_token)
        if name_start != -1:
            name_start += len(name_token)
            name_end = snippet.find("</span>", name_start)
            package_name = snippet[name_start:name_end].strip()
            package_names.append(package_name)
        start = end
    return package_names

def ensure_backticks(text: str) -> str:
    """Ensure that backticks are completed in the given text."""
    # Triple quotes first

    open_backticks = text.count("\n```")
    close_backticks = text.count("```\n")
    while open_backticks > close_backticks:
        text += "`"
        close_backticks += 1
    while close_backticks > open_backticks:
        text = "`" + text
        open_backticks += 1
    # Single quotes next
    open_backticks = text.count(" `")
    close_backticks = text.count("` ")
    while open_backticks > close_backticks:
        text += "`"
        close_backticks += 1
    while close_backticks > open_backticks:
        text = "`" + text
        open_backticks += 1
    return text


async def get_package_info(
    package_name,
    verbosity=0,
    include=None,
    release=None,
    client=None,
) -> "PackageInfo":
    """Retrieve detailed package information from PyPI JSON API."""
    if TYPE_CHECKING:
        from datetime import datetime
        from aiohttp import ClientSession as Client
        from mbpy.helpers._display import getconsole
        console = getconsole()
    else:
        datetime = smart_import("datetime.datetime")
        client = client or smart_import("aiohttp.ClientSession")()
        console = smart_import("mbpy.helpers._display").getconsole()



    package_url = f"https://pypi.org/pypi/{package_name}/json"
    response = await client.get(package_url)
    if response.status != 200:
        logging.warning(f"Package not found: {package_name}")
        return {}
    package_data: dict = deepcopy(await response.json())
    logging.debug("package_data")
    logging.debug(package_data)
    info = package_data.get("info", {})
    include = [include] if isinstance(include, str) else include or []
    try:
        if release or "all" in include:
            release = release or info.get("version", "")
            release_found = False
            for key in package_data.get("releases", {}):
                if release in key:
                    release_found = True
                    release_info = package_data.get("releases", {}).get(key, [{}])[0]
                    break
            if not release_found:
                releases = package_data.get("releases", {}).keys()
                preview = 4 if len(releases) > 8 else 2 if len(releases) > 4 else 1
                first = ", ".join(list(releases)[:preview])
                last = ", ".join(list(releases)[-preview:])
                color = "spring_green1"
                console.print(
                    f"[bold {color}]{package_name}[/bold {color}] release `{release}` not found in  {first} ... {last}",
                )
    except Exception as e:
        from mbpy.helpers._display import isverbose
        if isverbose():
            traceback.print_exc()
        logging.error(f"Error fetching release {release} for {package_name}: {e}")


    if release or "all" in include:
        if not release_info:
            raise ValueError(
                f"Package not found: {package_name} {'for release' + str(release) if release else ''}",
            )
        else:
            info.update({k:v for k,v in release_info.items() if v})

    releases = package_data.get("releases", {})

    if releases:
        releases = sorted(
            releases.items(),
            key=lambda x: x[1][0]["upload_time"] if len(x[1]) > 0 else "zzzzzzz",
            reverse=True,
        )

        if releases and len(releases[0][1]) > 0 and len(releases[-1][1]) > 0:
            latest, earliest = releases[0], releases[-1]
        else:
            latest, earliest = None, None

    else:
        latest, earliest = None, None

    package_info: "PackageInfo" = {
        "name": info.get("name", ""),
        "version": info.get("version", "").replace("-", "."),
        "summary": info.get("summary", ""),
        "latest_release": datetime.strptime(latest[1][0]["upload_time"], "%Y-%m-%dT%H:%M:%S").strftime("%b %d, %Y %I:%M %p") if latest else "",
        "author": info.get("author", ""),
        "earliest_release": {
            "version": earliest[0].replace("-", ".") if earliest else "",
            "upload_time": datetime.strptime(earliest[1][0]["upload_time"], "%Y-%m-%dT%H:%M:%S").strftime("%b %d, %Y %I:%M %p"),
            "requires_python": earliest[1][0].get("requires_python", ""),
        }
        if earliest
        else {},
        "urls": info.get("project_urls", info.get("urls", {})),
        "description": ensure_backticks(info.get("description", ""))[: verbosity * 250],
        "requires_python": info.get("requires_python", ""),
        "releases": [{release[0]: {"upload_time": datetime.strptime(release[1][0]["upload_time"], "%Y-%m-%dT%H:%M:%S").strftime("%b %d, %Y %I:%M %p")}} for release in releases]
        if releases and len(releases[0][1]) > 0
        else [],
    }

    if verbosity > 2 or "all" in include:
        package_info["description"] = info.get("description", "")

    project_urls: Dict[str, str] = info.get("project_urls", info.get("urls", {}))
    try:
        package_info["github_url"] = (
            next(
                (url for _, url in project_urls.items() if "github.com" in url.lower()),
                None,
            )
            or ""
        )
    except (StopIteration, TypeError, AttributeError):
        package_info["github_url"] = ""

    include = [include] if isinstance(include, str) else include or []
    if include and "all" in include:
        include = INFO_KEYS + ADDITONAL_KEYS

    for key in include:
        if key in ("releases", "release"):
            continue
        if key in ADDITONAL_KEYS:
            package_info[key] = package_data.get(key, {})
        elif key in INFO_KEYS:
            package_info[key] = info.get(key, "")
        else:
            raise ValueError(f"Invalid key: {key}")

    if not any(i in include for i in ("releases", "release","all")):
        package_info.pop("releases", None)
    return package_info

async def find_and_sort(
    query_key,
    limit=7,
    sort=None,
    verbosity=0,
    include=None,
    release=None,
) -> "AsyncGenerator[PackageInfo, None]":
    """Find and sort packages concurrently."""
    if TYPE_CHECKING:
        import asyncio
        from aiohttp import ClientSession as Client
    else:
        asyncio = smart_import("asyncio")
        Client = smart_import("aiohttp.ClientSession")

    try:
        tasks = []
        async with Client() as client:
            async with asyncio.TaskGroup() as tg:
                # Start fetching the query package info immediately
                query_task = tg.create_task(
                    get_package_info(query_key, verbosity, include, release, client),
                    name=f"query_{query_key}"
                )
                
                # Start getting package names without awaiting
                names_task = tg.create_task(
                    get_package_names(query_key, client),
                    name="get_names"
                )
                
                # Yield the query result first
                try:
                    package = await query_task
                    if package:
                        yield package
                except Exception as e:
                    logging.error(f"Error fetching query package info: {e}")
                
                # Now get the additional package names
                try:
                    package_names = await names_task
                    # Create tasks for additional packages
                    tasks = [
                        tg.create_task(
                            get_package_info(name, verbosity, include, release, client),
                            name=f"package_{name}"
                        )
                        for name in package_names 
                        if name != query_key
                    ]
                except Exception as e:
                    logging.error(f"Error fetching package names: {e}")
                    package_names = []
                    
                # Yield results as they complete
                for task in asyncio.as_completed(tasks):
                    try:
                        package = await task
                        if package:
                            yield package
                    except Exception as e:
                        logging.error(f"Error fetching package info: {e}")

    except Exception as e:
        from mbpy.helpers._display import isverbose

        if isverbose():
            traceback.print_exc()
        logging.debug(f"Error: {e}")
        yield {}

if __name__ == "__main__":
    import asyncio
    from rich.table import Table
    from rich.console import Console

    async def main():
        args = list(sys.argv[1:])
        if "-d"in args or "--debug" in args:
            logging.getLogger().setLevel(logging.DEBUG)
            args.remove("-d") if "-d" in args else args.remove("--debug")
        query = args[0] if len(args) > 1 else "python"
        source = args[1] if len(args) > 2 else "google"  # Changed default to ddg

        console = Console()
        Prompt = smart_import("rich.prompt.Prompt")
        
        try:
            results = await search_online(query, source)
            
            if not results:
                # Try fallback to DuckDuckGo if no results
                if source != 'ddg':
                    results = await search_online(query, 'ddg')
                
            if not results:
                console.print(f"\n[yellow]No results found for '[bold]{query}[/bold]' on any search engine[/yellow]")
                return

            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Title", style="cyan", no_wrap=False)
            table.add_column("URL", style="green", no_wrap=False) 
            table.add_column("Content", style="blue", no_wrap=False)

            for result in results:
                print(result["content"].getlines())
                # print(result["content"].data)
                content = "\n".join(result["content"].data)
                result["md"] = result["content"]
                if result.get('title') and result.get('url'):
                    table.add_row(
                        result['title'][:100] + ('...' if len(result['title']) > 100 else ''),
                        result['url'][:100] + ('...' if len(result['url']) > 100 else ''),
                        content[:100] + ('...' if len(content) > 100 else '')
                    )
              

            console.print("\n")
            console.print(table)
            console.print("\n")
            if (a:=Prompt.ask(f"Select Row:",choices=[str(i) for i in range(len(results))] + ["q"])) != "q":

                results[int(a)]["md"].stream()

        except Exception as e:
            console.print(f"\n[red]Error searching for '{query}': {str(e)}[/red]")
            traceback.print_exc()
            if logging.getLogger().level <= logging.DEBUG:
                console.print_exception()

    asyncio.run(main())
