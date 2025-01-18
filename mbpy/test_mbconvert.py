from pathlib import Path

import pytest
from fastjsonschema import validate

from mbpy.mbconvert import Dependency, MBConverter

MB_SCHEMA = {  
    "type": "object",  
    "properties": {  
        "dependencies": {  
            "type": "array",  
            "items": {  
                "type": "object",  
                "properties": {  
                    "name": {"type": "string"},  
                    "version": {"type": ["string", "null"]},  
                    "type": {"enum": ["pypi", "local", "system", "github"]},  
                    "path": {"type": ["string", "null"]},  
                    "repository": {"type": ["string", "null"]},  
                    "conditions": {"type": ["object", "null"]},
                    "extras": {"type": ["array", "string"], "items": {"type": "string"}},
                    "editable": {"type": "boolean"},
                    "upgrade": {"type": "boolean"},
                    "source": {"type": ["string", "null"]},
                    "min_version": {"type": ["string", "null"]},
                    "max_version": {"type": ["string", "null"]}  
                },  
                "required": ["name", "type"]  
            }  
        },  
        "environment": {  
            "type": "object",  
            "additionalProperties": {"type": ["string", "null"]}  
        }  
    },  
    "required": ["dependencies", "environment"]  
}  

@pytest.fixture  
def sample_config():  
    return """[tool.mb]  
deps = [  
    "requests>=2.0.0 ; python>='3.8'",  
    "./libs/mylib",  
    "pytorch/pytorch ; cuda=='11.8'",  
    "system:gcc",  
    "../shared/utils",  
    "fastapi>=0.70.0",  
]  
env = [  
    "DATABASE_URL",  
    "API_KEY=default_key",  
    "PYTHONPATH=./src:./libs",  
]  
"""  

@pytest.fixture  
def temp_config(sample_config, tmp_path):  
    config_path = tmp_path / "pyproject.toml"  
    with open(config_path, "w") as f:  
        f.write(sample_config)  
    return config_path  

@pytest.fixture  
def converter(temp_config):  
    return MBConverter(temp_config)  

class TestDependencyParsing:  
    @pytest.mark.parametrize("dep_str,expected", [  
        (  
            "requests>=2.0.0 ; python>='3.8'",  
            Dependency(spec="requests>=2.0.0", conditions="python>='3.8'")  
        ),  
        (  
            "./libs/mylib",  
            Dependency(spec="mylib", path=Path("./libs/mylib").resolve())  
        ),  
        (  
            "pytorch/pytorch ; cuda=='11.8'",  
            Dependency(spec="pytorch", repo="pytorch/pytorch", conditions="cuda=='11.8'")  
        ),  
        (  
            "system:gcc",  
            Dependency(spec="gcc", is_system=True)  
        )  
    ])  
    def test_parse_dependency(self, converter, dep_str, expected):  
        result = converter._parse_dependency(dep_str)  
        assert result.spec == expected.spec  
        assert result.conditions == expected.conditions  
        assert result.is_system == expected.is_system  
        if expected.path:  
            assert result.path == expected.path  
        assert result.repo == expected.repo  

class TestEnvironmentVariables:  
    def test_parse_env_vars(self, converter):  
        converter.parse_env_vars()  
        assert converter.env_vars == {  
            "DATABASE_URL": None,  
            "API_KEY": "default_key",  
            "PYTHONPATH": "./src:./libs"  
        }  

class TestIntermediateRepresentation:  
    def test_mb_to_ir(self, converter):  
        ir = converter.to_intermediate()  
        validate(MB_SCHEMA, ir)
        
        assert len(ir["dependencies"]) == 6  
        assert ir["dependencies"][0] == {  
            "name": "requests",  
            "type": "pypi",  
            "version": ">=2.0.0",  
            "conditions": {"python": ">=3.8"}  
        }  
        
        assert ir["dependencies"][2] == {  
            "name": "pytorch",  
            "type": "github",  
            "repository": "pytorch/pytorch",  
            "conditions": {"cuda": "11.8"}  
        }  

class TestNixGeneration:  
    def test_ir_to_nix(self, converter: MBConverter):  
        ir = converter.to_intermediate()  
        nix = converter.generate_nix(ir)  
        from rich import console
        console = console.Console()
        console.print(nix)
        assert "inputs.nixpkgs.url" in nix  
        assert "buildInputs" in nix  
        assert "shellHook" in nix  
        
        assert 'export DATABASE_URL' in nix  
        assert 'export API_KEY="default_key"' in nix  
        
        assert "ps.requests" in nix  
        assert "ps.fastapi" in nix  
        assert "pkgs.gcc" in nix  

    def test_complete_conversion(self, converter):  
        nix = converter.convert()  
        
        assert isinstance(nix, str)  
        assert 'description = "mb-workspace"' in nix
        assert "devShell" in nix  
        assert "buildInputs" in nix

class TestGenerateNix:
    def test_generate_nix_with_python_and_system_deps(self, converter: MBConverter):
        ir = {
            "name": "test-package",
            "version": "0.1.0",
            "description": "Test package",
            "dependencies": [
                {"name": "requests", "type": "pypi"},
                {"name": "gcc", "type": "system"}
            ],
            "environment": {}
        }
        nix = converter.generate_nix(ir)
        assert "ps.requests" in nix
        assert "pkgs.gcc" in nix

    def test_generate_nix_with_no_deps(self, converter: MBConverter):
        ir = {
            "name": "test-package",
            "version": "0.1.0",
            "description": "Test package",
            "dependencies": [],
            "environment": {}
        }
        nix = converter.generate_nix(ir)
        assert "# No Python dependencies" in nix
        assert "# No System dependencies" in nix

    def test_generate_nix_with_env_vars(self, converter: MBConverter):
        ir = {
            "name": "test-package",
            "version": "0.1.0",
            "description": "Test package",
            "dependencies": [],
            "environment": {
                "DATABASE_URL": None,
                "API_KEY": "default_key"
            }
        }
        nix = converter.generate_nix(ir)
        assert 'export DATABASE_URL="$DATABASE_URL"' in nix
        assert 'export API_KEY="default_key"' in nix

if __name__ == "__main__":  
    pytest.main([__file__, "-vv"])