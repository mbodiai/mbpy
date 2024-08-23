
from pathlib import Path
import tomlkit
from typing import Literal

getcwd = Path.cwd
WORKFLOW_UBUNTU = """name: "Ubuntu"

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: write
  pull-requests: write

jobs:
  ubuntu:
    name: ${{ matrix.os }}
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-20.04, ubuntu-latest]

    steps:
      - name: Checkout
        uses: actions/checkout@v3

      - name: Set up Python 3.11
        uses: actions/setup-python@v3
        with:
          python-version: 3.11

      - name: Run install script
        run: |
            python -m pip install --upgrade pip
            python -m pip install hatch

      - name: Cache packages
        uses: actions/cache@v3
        env:
          cache-name: cache-packages
        with:
          path: ~/.local/bin ~/.local/lib .mbodied/envs/mbodied
          key: ${{ runner.os }}-${{ env.cache-name }}-${{ hashFiles('install.bash') }}
          restore-keys: |
            ${{ runner.os }}-${{ env.cache-name }}-

      - name: Check disk usage
        run: df -h

      - name: Clean up before running tests
        run: |
          # Add commands to clean up unnecessary files
          sudo apt-get clean
          sudo rm -rf /usr/share/dotnet /etc/mysql /etc/php /etc/apt/sources.list.d
          # Add more cleanup commands as needed

      - name: Check disk usage after cleanup
        run: df -h

      - name: Run tests
        run: |
          hatch run pip install '.'
          hatch run test"""

WORKFLOW_MAC = """name: "MacOS | Python 3.12|3.11|3.10"

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pull-requests: write

jobs:
  test:
    name: Python ${{ matrix.python-version }}
    runs-on: macos-latest
    strategy:
      matrix:
        python-version: ["3.12", "3.11", "3.10"]

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v3
        with:
          python-version: ${{ matrix.python-version }}

      - name: Run install script
        run: |
            python -m pip install --upgrade pip
            python -m pip install hatch

      - name: Cache packages
        uses: actions/cache@v3
        env:
          cache-name: cache-packages
        with:
          path: ~/Library/Caches/Homebrew
          key: ${{ runner.os }}-${{ env.cache-name }}-${{ hashFiles('install.bash') }}
          restore-keys: |
            ${{ runner.os }}-${{ env.cache-name }}-
      - name: Run tests
        run: |
          hatch run pip install '.'
          hatch run test"""


def create_project(
    project_name,
    author,
    description="",
    deps: list[str] | Literal["local"] | None = None,
    python_version="3.11",
    add_cli=True,
) -> None:
    print(f"Creating project: {project_name}")
    print(f"Author: {author}")
    print(f"Description: {description}")
    print(f"Dependencies: {deps}")
    print(f"Python version: {python_version}")
    print(f"Add CLI: {add_cli}")

    if deps is None:
        deps = []
    
    # Create project root directory
    root = Path(getcwd())
    project_root = root
    if root.stem != project_name:
        project_root = root / project_name
        print(f"Creating project root directory: {project_root}")
    project_root.mkdir(exist_ok=True, parents=True)
    
    # Create main directories
    dirs = ["assets", "docs", "tests", project_name]
    for dir in dirs:
        (project_root / dir).mkdir(exist_ok=True, parents=True)
        if dir != project_name:
            (project_root / dir / ".gitkeep").touch(exist_ok=True)
    # Create workflows directory
    workflows = project_root / ".github" / "workflows"
    workflows.mkdir(exist_ok=True, parents=True)

    resources = project_root / "resources"
    resources.mkdir(exist_ok=True, parents=True)
    (resources / ".gitkeep").touch(exist_ok=True)
    # Create __about__.py in project directory
    about_file = project_root / project_name / "__about__.py"
    about_content = '__version__ = "0.0.1"'
    about_file.write_text(about_content)

    # Create __init__.py and main.py in project directory if add_cli is True
    if add_cli:
        init_content = "from .main import cli\n\n__all__ = ['cli']"
        main_content = "from click import command\n\n@command()\ndef cli() -> None:\n    pass\n\nif __name__ == '__main__':\n    cli()"
        (project_root / project_name / "__init__.py").write_text(init_content)
        (project_root / project_name / "main.py").write_text(main_content)
    else:
        (project_root / project_name / "__init__.py").touch()

    # Create pyproject.toml content
    pyproject_content = create_pyproject_toml(project_name, author, description, deps, python_version=python_version, add_cli=add_cli)

    # Create files in root
    files = [
        ("LICENSE", ""),
        (
            "README.md",
            f"# {project_name}\n\n{description}\n\n## Installation\n\n```bash\npip install {project_name}\n```\n",
        ),
        ("pyproject.toml", pyproject_content),
        ("requirements.txt", "click" if add_cli else ""),
    ]
    for file, content in files:
        file_path = project_root / file
        file_path.write_text(content)

    # Create workflow files
    (workflows / "macos.yml").write_text(WORKFLOW_MAC)
    (workflows / "ubuntu.yml").write_text(WORKFLOW_UBUNTU)


def create_pyproject_toml(
    project_name,
    author,
    desc="",
    deps=None,
    python_version="3.10",
    add_cli=True,
    existing_content=None,
    **kwargs
) -> str:
    """Create a pyproject.toml file for a Hatch project."""
    if existing_content:
        pyproject = tomlkit.parse(existing_content)
    else:
        pyproject = tomlkit.document()

    # Update build-system
    build_system = pyproject.setdefault("build-system", {})
    build_system["requires"] = ["hatchling"]
    build_system["build-backend"] = "hatchling.build"

    # Update project
    project = pyproject.setdefault("project", {})
    project["name"] = project_name
    project["dynamic"] = ["version"]
    project["description"] = desc if desc else project.get("description", "")
    project["readme"] = "README.md"
    project["requires-python"] = f">={python_version}"
    project["license"] = "apache-2.0"
    project["keywords"] = []
    project["authors"] = [{"name": a.strip()} for a in author.split(",")]

    # Update classifiers
    classifiers = [
        "Development Status :: 4 - Beta",
        "Programming Language :: Python",
    ]
    classifiers.extend([f"Programming Language :: Python :: 3.{v}" for v in range(int(python_version.split('.')[1]), 13)])
    classifiers.extend([
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
    ])
    project["classifiers"] = classifiers

    # Update dependencies
    existing_deps = project.get("dependencies", [])
    new_deps = deps or []
    all_deps = list(set(existing_deps + new_deps))
    all_deps.sort(key=lambda x: x.lower())
    project["dependencies"] = all_deps

    # Update optional dependencies
    optional_deps = project.setdefault("optional-dependencies", {})

    # Update project URLs
    project["urls"] = {
        "Documentation": f"https://github.com/{author}/{project_name}#readme",
        "Issues": f"https://github.com/{author}/{project_name}/issues",
        "Source": f"https://github.com/{author}/{project_name}",
    }

    # Update project scripts
    if add_cli:
        project["scripts"] = {project_name: f"{project_name}:cli"}

    # Update tool configurations
    tool = pyproject.setdefault("tool", {})
    
    # Hatch configuration
    hatch = tool.setdefault("hatch", {})
    hatch["version"] = {"path": f"{project_name}/__about__.py"}
    hatch["metadata"] = {"allow-direct-references": True}
    hatch["build"] = {"targets": {"wheel": {"force-include": {"resources": f"{project_name}/resources"}}}}
    
    hatch_envs = hatch.setdefault("envs", {})
    default_env = hatch_envs.setdefault("default", {})
    default_env["python"] = python_version
    default_env["path"] = f".envs/{project_name}"
    default_env["dependencies"] = ["pytest", "pytest-mock", "pytest-asyncio"]
    default_env["scripts"] = {
        "test": f"pytest -vv --ignore third_party {{args:tests}}",
        "test-cov": "coverage run -m pytest {{args:tests}}",
        "cov-report": ["- coverage combine", "coverage report"],
        "cov": ["test-cov", "cov-report"],
    }

    conda_env = hatch_envs.setdefault("conda", {})
    conda_env["type"] = "conda"
    conda_env["python"] = python_version
    conda_env["command"] = "conda"
    conda_env["conda-forge"] = False
    conda_env["environment-file"] = "environment.yml"
    conda_env["prefix"] = ".venv/"

    hatch_envs["all"] = {"matrix": [{"python": ["3.10", "3.11", "3.12"]}]}

    types_env = hatch_envs.setdefault("types", {})
    types_env["dependencies"] = ["mypy>=1.0.0"]
    types_env["scripts"] = {"check": f"mypy --install-types --non-interactive {{args:{project_name}/ tests}}"}

    # Coverage configuration
    coverage = tool.setdefault("coverage", {})
    coverage["run"] = {
        "source_pkgs": [project_name, "tests"],
        "branch": True,
        "parallel": True,
        "omit": [f"{project_name}/__about__.py"],
    }
    coverage["paths"] = {
        project_name: [f"{project_name}/"],
        "tests": ["tests"],
    }
    coverage["report"] = {
        "exclude_lines": ["no cov", "if __name__ == .__main__.:", "if TYPE_CHECKING:"],
    }

    # Ruff configuration
    ruff = tool.setdefault("ruff", {})
    ruff["line-length"] = 120
    ruff["indent-width"] = 4
    ruff["target-version"] = f"py{python_version.replace('.', '')}"

    ruff_lint = ruff.setdefault("lint", {})
    ruff_lint["extend-unsafe-fixes"] = ["ALL"]
    ruff_lint["select"] = [
        "A", "C4", "D", "E", "F", "UP", "B", "SIM", "N", "ANN", "ASYNC",
        "S", "T20", "RET", "SIM", "ARG", "PTH", "ERA", "PD", "I", "PLW",
    ]
    ruff_lint["ignore"] = [
        "D100", "D101", "D104", "D106", "ANN101", "ANN102", "ANN003", "UP009", "ANN204",
        "B026", "ANN001", "ANN401", "ANN202", "D107", "D102", "D103", "E731", "UP006",
        "UP035", "ANN002", "PLW2901", "UP035", "UP006",
    ]
    ruff_lint["fixable"] = ["ALL"]
    ruff_lint["unfixable"] = []

    ruff["format"] = {
        "docstring-code-format": True,
        "quote-style": "double",
        "indent-style": "space",
        "skip-magic-trailing-comma": False,
        "line-ending": "auto",
    }

    ruff_lint["pydocstyle"] = {"convention": "google"}

    ruff_lint["per-file-ignores"] = {
        "**/{tests,docs}/*": ["ALL"],
        "**__init__.py": ["F401"],
    }

    return tomlkit.dumps(pyproject)


