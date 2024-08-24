#!/bin/bash

# Exit on error
set -e

# Clone the repository
git clone https://github.com/mbodiai/embodied-data.git
cd embodied-data

# Create the project using mbpy create
mbpy create embodied-data "mbodiai" "A library for embodied data processing" --doc-type mkdocs

# Set up the documentation
cd embodied-data
mkdocs build

# Install the project in editable mode
pip install -e .

# Run the tests
pytest

echo "Project setup complete!"
