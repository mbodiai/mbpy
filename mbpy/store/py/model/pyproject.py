from types import ModuleType
from typing import Dict, List, cast

from pydantic import BaseModel, Field

from mbpy import DataModel


class ProjectUrlsModel(DataModel):
    Documentation: str | None
    Repository: str | None
    Changelog: str | None
    Issues: str | None
    Homepage: str | None
    Download: str | None
    Funding: str | None


class EntryPointsModel(DataModel):
    console_scripts: List[str] | None
    gui_scripts: List[str] | None


class ProjectModel(DataModel):
    name: str
    version: str
    description: str
    readme: str
    requires_python: str
    license: Dict[str, str]
    authors: List[Dict[str, str]]
    maintainers: List[Dict[str, str]] | None
    classifiers: List[str]
    keywords: List[str] | None
    dependencies: List[str] | None
    optional_dependencies: Dict[str, List[str]] | None
    entry_points: EntryPointsModel | None
    urls: ProjectUrlsModel | None


class BuildSystemModel(DataModel):
    requires: List[str]
    build_backend: str = Field(alias="build-backend")


class PyProjectTomlModel(DataModel):
    build_system: BuildSystemModel
    project: ProjectModel
