from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import toml



# Mock function to generate flake.nix in correct Nix DSL format
def generate_flake_with_git_refs(toml_path):
    workspace_dir = toml_path.parent
    config = toml.load(toml_path)["tool"]["mb"]["workspace"]

    flake_path = workspace_dir / "flake.nix"
    flake_content = """
{
  description = "Workspace dynamically generated from pyproject.toml with @ Git dependencies";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-23.05";
    repo.url = "https://github.com/example/repo.git@main";
    arm_dep.url = "https://github.com/arch-specific/arm_dep.git@v1.0";
    utilities.url = "https://github.com/mbody/utilities.git@main";
  };

  outputs = { self, nixpkgs, ... }:
    let
      pkgs = import nixpkgs {
        system = "x86_64-linux";
      };
    in {
      devShell.x86_64-linux = pkgs.mkShell {
        buildInputs = [
          pkgs.pythonPackages.numpy
          pkgs.pythonPackages.scipy
          ./local_cpp_project
          pkgs.cmake_3_24
          pkgs.gcc_12
          pkgs.python311
        ];
        nativeBuildInputs = [ pkgs.cmake pkgs.gcc ];
        shellHook = ''
          export MY_ENV_VAR=example_value
          export CUSTOM_VAR=custom_value
        '';
      };
    };
}
"""
    with flake_path.open("w") as f:
        f.write(flake_content.strip())


@pytest.fixture
def pyproject_path():
    """Fixture to create a temporary pyproject.toml file."""
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        pyproject_content = """
        [tool.mb.workspace]
        env = { MY_ENV_VAR = "example_value", CUSTOM_VAR = "custom_value" }
        cpp = "20"
        gcc = "12"
        cmake = "3.24"
        python = {
            version = "3.10",
            runtime = "pypy"
        }
        

        [tool.mb.workspace.dependencies]
        git = ["example/repo@main", "arch-specific/arm_dep@v1.0"]
        local = ["./local_cpp_project"]
        cmake = { "3.24" = ["mbody/utilities@main"], "3.18" = ["older/cmake_dep@main"] }
        numpy = { 
            "x86_64-linux" = ["arch-specific/x86_dep@main"],
            "aarch64-darwin" = ["arch-specific/arm_dep@v1.0"] 
        }
        """
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text(pyproject_content)
        yield pyproject_file


def test_generate_flake(pyproject_path):
    """Test the generation of flake.nix."""
    generate_flake_with_git_refs(pyproject_path)

    flake_path = pyproject_path.parent / "flake.nix"
    assert flake_path.exists()

    with flake_path.open("r") as f:
        generated_flake = f.read().strip()

    # Expected flake.nix content in Nix DSL format
    expected_flake = """
{
  description = "Workspace dynamically generated from pyproject.toml with @ Git dependencies";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-23.05";
    mb.url = "https://github.com/mbodiai/mb.git@main";
    data.url = "https://github.com/mbodiai/embodied-data.git@again";
  };

  outputs = { self, nixpkgs, ... }:
    let
      pkgs = import nixpkgs {
        system = "x86_64-linux";
      };
    in {
      devShell.x86_64-linux = pkgs.mkShell {
        buildInputs = [
          pkgs.pythonPackages.numpy
          pkgs.pythonPackages.scipy
          ./local_cpp_project
          pkgs.cmake_3_24
          pkgs.gcc_12
          pkgs.python311
        ];
        nativeBuildInputs = [ pkgs.cmake pkgs.gcc ];
        shellHook = ''
          export MY_ENV_VAR=example_value
          export CUSTOM_VAR=custom_value
        '';
      };
    };
}
""".strip()

    assert generated_flake == expected_flake, "Generated flake.nix does not match expected output."
