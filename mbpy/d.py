import os
import json
import requests
from urllib.parse import urljoin, urlparse

def download_schema(url, output_dir, downloaded=None):
    if downloaded is None:
        downloaded = set()

    # Skip if already downloaded
    if url in downloaded:
        return

    print(f"Downloading: {url}")
    response = requests.get(url)
    response.raise_for_status()

    # Save schema locally
    parsed_url = urlparse(url)
    local_filename = os.path.join(output_dir, os.path.basename(parsed_url.path))
    with open(local_filename, 'w') as file:
        json.dump(response.json(), file, indent=2)

    downloaded.add(url)

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


def download_schema_in_json(schema, base_url, output_dir, downloaded):
    """Helper function to handle recursive references in JSON objects."""
    if isinstance(schema, dict):
        for key, value in schema.items():
            if key == "$ref" and isinstance(value, str):
                ref_url = urljoin(base_url, value)
                download_schema(ref_url, output_dir, downloaded)
            elif isinstance(value, dict):
                download_schema_in_json(value, base_url, output_dir, downloaded)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        download_schema_in_json(item, base_url, output_dir, downloaded)


if __name__ == "__main__":
    # Starting schema URL and output directory
    root_schema_url = "https://json.schemastore.org/pyproject.json"
    output_directory = "schemas"

    os.makedirs(output_directory, exist_ok=True)
    download_schema(root_schema_url, output_directory)

    print("All schemas downloaded and saved in the 'schemas' directory.")