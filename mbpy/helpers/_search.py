import logging
import re
from types import SimpleNamespace
import urllib.parse

import click
import requests
from bs4 import BeautifulSoup
from mrender.md import Markdown
from rich import print
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.text import Span, Text

log = logging.getLogger()
import json
console = Console(style="bold white on cyan1", soft_wrap=True)
blue_console = Console(style="bold white on blue", soft_wrap=True)
print = lambda *args, **kwargs: console.print(*(Panel(Text(str(arg),style="red", overflow="fold")) for arg in args), **kwargs) # noqa
def print_bold(*args, **kwargs):
    return console.print(*(Panel(Text(str(arg), style="bold", overflow="fold")) for arg in args), **kwargs)
input = lambda arg, **kwargs: Confirm.ask(Text(str(arg), spans=[Span(0, 100, "blue")]), console=blue_console, default="y", **kwargs) # noqa
ask = lambda arg, **kwargs: Prompt.ask(Text(str(arg), spans=[Span(0, 100, "blue")]), console=blue_console, **kwargs) # noqa


def is_valid_url(url) -> bool:
    regex = re.compile(
        r'^(?:http|ftp)s?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(regex, url) is not None




def get_json(json_string: str):
    """
    Splits input into a list where each element is either a plain text string or a valid JSON object.
    Only parses JSON content inside curly braces and treats everything else as plain text.
    """

    class JSONRepairFSM:
        def __init__(self):
            self.current_chunk = []  # Current chunk being processed
            self.chunks = []  # List to store chunks (strings or JSON objects)
            self.state = "outside"  # Start outside of JSON structures
            self.stack = []  # Stack to manage nested structures

        def process_char(self, char):
            """
            Process a single character based on the current state.
            """
            if self.state == "outside":
                if char == "{":
                    # If we encounter a '{', finalize the current text chunk
                    if self.current_chunk:
                        self.chunks.append("".join(self.current_chunk).strip())
                        self.current_chunk = []
                    self.stack.append("dict")
                    self.state = "inside"
                    self.current_chunk.append(char)
                else:
                    # Keep appending the plain text characters
                    self.current_chunk.append(char)

            elif self.state == "inside":
                if char == "}":
                    self.stack.pop()
                    self.current_chunk.append(char)
                    if not self.stack:
                        # We've closed a JSON object, attempt to parse it
                        try:
                            json_obj = json.loads("".join(self.current_chunk))
                            self.chunks.append(json_obj)
                        except json.JSONDecodeError:
                            self.chunks.append("".join(self.current_chunk))
                        self.current_chunk = []
                        self.state = "outside"
                else:
                    self.current_chunk.append(char)

        def finalize(self):
            """
            Finalize the remaining content after processing.
            """
            if self.current_chunk:
                self.chunks.append("".join(self.current_chunk).strip())
            return self.chunks

        def repair(self, json_string):
            """
            Process the entire input and return the result.
            """
            for char in json_string:
                self.process_char(char)
            return self.finalize()

    fsm = JSONRepairFSM()
    return fsm.repair(json_string)

def html_to_markdown(element, level=0):
    from rich import inspect as rich_inspect
    # rich_inspect(element)
    
    return Markdown(get_json(element.text))

def extract_links(text):
    # Define the regular expression pattern for URLs
    url_pattern = re.compile(
        r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
    )

    # Find all matches in the text
    links = re.findall(url_pattern, text)

    return links


def browse(urls, timeout=25, interactive=False):
    log.debug(f"browse function called with urls: {urls}, timeout: {timeout}, interactive: {interactive}")
    results = []
    for i, url in enumerate(urls):
        try:
            log.debug(f"Sending GET request to {url}")
            response = requests.get(url, timeout=timeout)
            log.debug(f"Response status code: {response.status_code}")
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html5lib')

            title = soup.title.string if soup.title else "No title found"
            markdown_content = html_to_markdown(soup.body)
            
            result = {
                'url': url,
                'title': title,
                'content': markdown_content,
            }
            results.append(result)
            
            log.info(f"Processed: {url}")
        except requests.exceptions.RequestException as e:
            log.error(f"Error fetching the webpage {url}: {str(e)}")
            error_message = f"Error fetching the webpage: {e.response.status_code if hasattr(e, 'response') else str(e)}"
            results.append({
                'url': url,
                'error': error_message,
            })
        except Exception as e:
            log.error(f"Unexpected error while browsing {url}: {str(e)}")
            log.exception("Exception traceback:")
            results.append({
                'url': url,
                'error': f"Error browsing {url}: {str(e)}",
            })

    return results

@click.command()
@click.argument("urls", nargs=-1)
def main(urls) -> None:
    urls = urls or ["https://github.com"]
    res = browse(urls)
    for r in res:
        Markdown(html_to_markdown(SimpleNamespace(**r['content']))).stream()
if __name__ == "__main__":
    main()
