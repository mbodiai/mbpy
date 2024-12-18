from __future__ import annotations

import logging
import os
import shutil
from collections.abc import Sequence
from dataclasses import MISSING, asdict, dataclass, fields
from functools import cached_property
from pathlib import Path
from subprocess import run
from typing import Any

import pathspec
from hatchling.builders.hooks.plugin.interface import BuildHookInterface

log = logging.getLogger(__name__)


class BuildScriptsHook(BuildHookInterface):
    PLUGIN_NAME = "build-scripts"

    def initialize(
        self,
        version: str,  # noqa: ARG002
        build_data: dict[str, Any],
    ) -> None:
        created: set[Path] = set()

        all_scripts = 

        for script in all_scripts:
            if script.clean_out_dir:
                out_dir = Path(self.root, script.out_dir)
                log.debug(f"Cleaning {out_dir}")
                shutil.rmtree(out_dir, ignore_errors=True)
            elif script.clean_artifacts:
                for out_file in script.out_files(self.root):
                    log.debug(f"Cleaning {out_file}")
                    out_file.unlink(missing_ok=True)

        for script in all_scripts:
            log.debug(f"Script config: {asdict(script)}")
            work_dir = Path(self.root, script.work_dir)
            out_dir = Path(self.root, script.out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)

            for cmd in script.commands:
                log.info(f"Running command: {cmd}")
                run(cmd, cwd=str(work_dir), check=True, shell=True)  # noqa: S602

            log.info(f"Copying artifacts to {out_dir}")
            for work_file in script.work_files(self.root, relative=True):
                src_file = work_dir / work_file
                out_file = out_dir / work_file
                log.debug(f"Copying {src_file} to {out_file}")
                if src_file not in created:
                    out_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(src_file, out_file)
                    created.add(out_file)
                else:
                    log.debug(f"Skipping {src_file} - already exists")

            build_data["artifacts"].append(str(out_dir.relative_to(self.root)))





@dataclass
class BuildConfig:
    """A configuration for a single build script."""

    commands: Sequence[str]
    """The commands to run"""

    build_dir: str = "build"
    """Git file patterns relative to the work_dir to save as build artifacts"""

    install_dir: str = "/usr/local/lib/mb/"
    """The path where build artifacts will be saved"""

    def __post_init__(self) -> None:
        self.install_dir = conv_path(self.install_dir)

    def out_files(self) -> Sequence[Path]:
        """Get files in the output directory that match the artifacts spec."""
        d = Path(self.build_dir)
        return list(d.glob("*")) if d.exists() else []



def conv_path(path: str) -> str:
    """Convert a unix path to a platform-specific path."""
    return path.replace("/", os.sep)
