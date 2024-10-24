import sys

from tomlkit import dump, load

from mbpy.mpip import find_toml_file


def bump():
    toml = find_toml_file()
    parent = toml.parent
    with toml.open("r") as f:
        data = load(f)
        proj = data.get("project")
        if not proj:
            raise ValueError(f"No project section found in toml file. Found {data.keys()}")
        dynamic = proj.get("dynamic")
        if dynamic and "version" in dynamic:
            name: str = proj.get("name")
            about = parent / name / "__about__.py"
            version = about.read_text().split()
            maj, min, micro = sys._version_info(*version)
            version = f"{maj}.{min}.{int(micro)+1}"
            about.write_text(f"__version__ = {version}")
        elif "version" in proj and proj.get("version"):
            maj, min, micro = proj.get("version").split(".")
            version = f"{maj}.{min}.{int(micro)+1}"
            proj["version"] = version
        else:
            raise ValueError(f"Version not found in toml file. Found {proj.keys()}")
        with toml.open("w") as f:
            dump(data, f)
        return version


if __name__ == "__main__":
  from rich.console import Console
  console = Console(style="light_goldenrod2")
  console.print("Bumping version...")
  version = bump()
  console.print(f"Bumped to [bold]{version}[/bold]",style="light_goldenrod2")