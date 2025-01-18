"""setuptools.command.clean

Implements the Setuptools 'clean' command with rich_click."""

import os
import logging
import click
from shutil import rmtree as remove_tree

# Configure logging
log = logging.getLogger(__name__)

@click.command()
@click.option('--build-base', '-b', default='build', help="Base build directory")
@click.option('--build-lib', default='build/lib', help="Build directory for all modules")
@click.option('--build-temp', '-t', default='build/temp', help="Temporary build directory")
@click.option('--build-scripts', default='build/scripts', help="Build directory for scripts")
@click.option('--bdist-base', default='bdist', help="Temporary directory for built distributions")
@click.option('--all', '-a', is_flag=True, help="Remove all build output, including egg and .so files")
def clean(build_base, build_lib, build_temp, build_scripts, bdist_base, all):
    """Clean up build artifacts."""
    directories = [build_temp]
    if all:
        directories.extend([build_lib, bdist_base, build_scripts])

        for root, dirs, files in os.walk('.'):
            for file in files:
                if file.endswith(('.egg', '.so')):
                    file_path = os.path.join(root, file)
                    try:
                        os.remove(file_path)
                        log.info(f"Removed file: {file_path}")
                    except OSError:
                        log.warn(f"Could not remove file: {file_path}")

    for directory in directories:
        if os.path.exists(directory):
            remove_tree(directory, dry_run=False)
            log.info(f"Removed directory: {directory}")
        else:
            log.debug(f"'{directory}' does not exist -- can't clean it")

    # Attempt to remove the base build directory
    try:
        os.rmdir(build_base)
        log.info(f"Removed base build directory: {build_base}")
    except OSError:
        pass
