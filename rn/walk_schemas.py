import json
import logging
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
import rich_click as click
from rich.logging import RichHandler

logging.getLogger().addHandler(RichHandler())
logging.getLogger().setLevel(logging.INFO)  # Set to DEBUG for verbose output                                                                                                                                                                                       ws



def save_schema(schema, file_path) -> None:
    logging.info(f"Saving schema to: {file_path}")
    with Path(file_path).open("w") as file:
        json.dump(schema, file, indent=2)


def download_schema(url, output_dir, downloaded=None, resolve_nested=True) -> None:
    if downloaded is None:
        downloaded = set()

    # Skip if already downloaded
    if url in downloaded:
        return

    parsed_url = urlparse(url)
    if parsed_url.scheme in ("http", "https"):
        logging.info(f"Downloading: {url}")
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        # Save schema locally
        local_filename = Path(output_dir) / Path(parsed_url.path).name
        save_schema(response.json(), local_filename)

        downloaded.add(url)

        if resolve_nested:
            # Recursively resolve references
            schema = response.json()
            if isinstance(schema, dict):
                for key, value in schema.items():
                    if key == "$ref" and isinstance(value, str):
                        ref_url = urljoin(url, value)
                        download_schema(ref_url, output_dir, downloaded)
                    elif isinstance(value, dict):
                        download_schema_in_json(value, url, output_dir, downloaded)
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict):
                                download_schema_in_json(item, url, output_dir, downloaded)
    else:
        process_local_schema(url, output_dir, downloaded, resolve_nested)


def download_schema_in_json(schema, base_url, output_dir, downloaded, resolve_nested=True) -> None:
    """Helper function to handle recursive references in JSON objects."""
    if isinstance(schema, dict):
        for key, value in schema.items():
            if key == "$ref" and isinstance(value, str):
                ref_url = urljoin(base_url, value)
                if urlparse(ref_url).scheme in ("http", "https"):
                    download_schema(ref_url, output_dir, downloaded, resolve_nested)
                else:
                    process_local_schema(ref_url, output_dir, downloaded, resolve_nested)
            elif isinstance(value, dict):
                download_schema_in_json(value, base_url, output_dir, downloaded, resolve_nested)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        download_schema_in_json(item, base_url, output_dir, downloaded, resolve_nested)


def process_local_schema(file_path, output_dir, downloaded=None, resolve_nested=True) -> None:
    if downloaded is None:
        downloaded = set()

    if file_path in downloaded:
        return

    logging.info(f"Processing local schema: {file_path}")
    file_path, fragment = file_path.split("#", 1) if "#" in file_path else (file_path, None)
    with Path(file_path).open() as file:
        schema = json.load(file)

    if fragment:
        for part in fragment.split("/")[1:]:
            schema = schema.get(part)

    downloaded.add(file_path)

    # Create a directory for fragments if it doesn't exist
    base_name = Path(file_path).stem
    fragment_dir = Path(output_dir) / (base_name + "_fragments")
    if not fragment_dir.exists():
        fragment_dir.mkdir(parents=True)

    # Save the processed schema
    fragment_name = fragment.split("/")[-1] if fragment else base_name
    local_filename = (fragment_dir / fragment_name).with_suffix(".json")
    save_schema(schema, local_filename)

    if resolve_nested and isinstance(schema, dict):
            for key, value in schema.items():
                if key == "$ref" and isinstance(value, str):
                    ref_path = Path(file_path).parent / value
                    process_local_schema(ref_path, output_dir, downloaded, resolve_nested)
                elif isinstance(value, dict):
                    download_schema_in_json(value, file_path, output_dir, downloaded, resolve_nested)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            download_schema_in_json(item, file_path, output_dir, downloaded, resolve_nested)




@click.command("walk_schema")
@click.argument("url_or_path")
@click.option("--output-directory", "-o", default="schemas", help="Output directory for downloaded schemas.")
@click.option("--resolve-nested/--no-resolve-nested", default=True, help="Flag to control nested schema resolution.")
def main(url_or_path, output_directory, resolve_nested) -> None:
    walk_schema(url_or_path, output_directory, resolve_nested) 
    
def walk_schema(url_or_path, output_directory, resolve_nested) -> None:
    if not Path(output_directory).exists():
        Path(output_directory).mkdir(parents=True)
    if Path(url_or_path).exists():
        process_local_schema(url_or_path, output_directory, resolve_nested=resolve_nested)
    else:
        download_schema(url_or_path, output_directory, resolve_nested=resolve_nested)


if __name__ == "__main__":
    main()
