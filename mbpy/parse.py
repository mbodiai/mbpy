from pathlib import Path

import toml

from mbpy.store.py.model.pyproject import PyProject


class PyProjectParser:
    def __init__(self, toml_path):
        self.toml_path = Path(toml_path)
        self.config = None

    def parse(self):
        """Parse the pyproject.toml file and return a structured dictionary."""
        try:
            raw_config = toml.load(self.toml_path)
            workspace = raw_config["tool"]["mb"]["workspace"]
        except KeyError as e:
            raise KeyError(f"Missing required configuration in pyproject.toml: {e}")

        # Handle shorthand and normalize keys
        normalized_config = self._normalize_workspace(workspace)
        self.config = normalized_config
        return normalized_config

    def _normalize_workspace(self, workspace):
        """Normalize the workspace configuration, including shorthand handling."""
        # Normalize cpp version shorthand (e.g., 20 -> "c++20")
        if "cpp" in workspace and isinstance(workspace["cpp"], int):
            workspace["cpp"] = f"c++{workspace['cpp']}"

        # Flatten dependencies for easier handling
        if "deps" in workspace:
            workspace["deps"] = self._normalize_dependencies(workspace["deps"])

        # Return normalized workspace
        return workspace

    def _normalize_dependencies(self, deps):
        """Normalize dependencies (e.g., pip, conda, git, local)."""
        normalized = {}
        for name, value in deps.items():
            if isinstance(value, str):
                # Pip and Conda are strings (e.g., "pip" or "conda")
                normalized[name] = {"type": value}
            elif isinstance(value, dict):
                # Git and Local are dictionaries (e.g., {"git": "..."} or {"local": "..."})
                normalized[name] = value
            else:
                raise ValueError(f"Unsupported dependency format: {name} = {value}")
        return normalized

    def dump_config(self):
        """Print the parsed and normalized configuration for debugging."""
        if self.config:
            import pprint

            pprint.pprint(self.config)
        else:
            print("No configuration parsed yet.")


# Example usage
if __name__ == "__main__":
    # Replace with your actual pyproject.toml path
    toml_path = "test.toml"
    parser = PyProjectParser(toml_path)

    try:
        parsed_config: PyProject = parser.parse()
        print("Parsed Configuration:")
        parser.dump_config()
    except Exception as e:
        print(f"Error: {e}")
