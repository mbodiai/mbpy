from dataclasses import dataclass  
from pathlib import Path  
from typing import Dict, Final, List, Optional, Any, Tuple  
import tomlkit
import os  

@dataclass  
class Dependency:  
    spec: str  
    conditions: Optional[str] = None  
    path: Optional[Path] = None  
    repo: Optional[str] = None  
    is_system: bool = False  

CONTROL_ESCAPE: Final = {
    7: "\\a",
    8: "\\b",
    11: "\\v",
    12: "\\f",
    13: "\\r",
}
def escape_control_codes(
    text: str,
    _translate_table: Dict[int, str] = CONTROL_ESCAPE,
) -> str:
    r"""Replace control codes with their "escaped" equivalent in the given text.
    
    (e.g. "\b" becomes "\\b")

    Args:
        text (str): A string possibly containing control codes.

    Returns:
        str: String with control codes replaced with their escaped version.
    """
    return text.translate(_translate_table)     


class MBConverter:  
    def __init__(self, config_path: Path):  
        self.config_path = config_path  
        self.config = self._load_config()  
        self.deps: List[Dependency] = []  
        self.env_vars: Dict[str, Optional[str]] = {}  
        
    def _load_config(self) -> Dict:  
        with Path(self.config_path).open("rb") as f:
            config = tomlkit.load(f)  
        return config.get('tool', {}).get('mb', {})  
    
    def _parse_dependency(self, dep_str: str) -> Dependency:  
        parts = dep_str.split(';', 1)  
        spec = parts[0].strip()  
        condition = parts[1].strip() if len(parts) > 1 else None  

        if spec.startswith('system:'):  
            return Dependency(spec=spec[7:], conditions=condition, is_system=True)  

        if spec.startswith('./') or spec.startswith('../') or spec.startswith('/'):  
            return Dependency(spec=Path(spec).name, conditions=condition, path=Path(spec).resolve())  

        if '/' in spec and not spec.startswith(('http://', 'https://', 'git+')):  
            return Dependency(spec=spec.split('/')[-1], conditions=condition, repo=spec)  

        return Dependency(spec=spec, conditions=condition)  
    
    def parse_env_vars(self) -> None:  
        for env in self.config.get('env', []):  
            if '=' in env:  
                key, value = env.split('=', 1)  
                self.env_vars[key.strip()] = value.strip()  
            else:  
                self.env_vars[env.strip()] = None  
    
    def _parse_conditions(self, conditions: Optional[str]) -> Optional[Dict[str, str]]:  
        if not conditions:  
            return None  
        
        result = {}  
        try:  
            for condition in conditions.split('and'):  
                condition = condition.strip()  
                if '==' in condition:  
                    key, value = condition.split('==', 1)  
                    result[key.strip()] = value.strip().strip("'\"")  
                elif '>=' in condition:  
                    key, value = condition.split('>=', 1)  

                    result[key.strip()] = ">=" + escape_control_codes(value.strip().strip("'\""))
                else:  
                    pass  
        except ValueError:  
            return None  
        return result  
    
    def _split_version(self, spec: str) -> Tuple[str, Optional[str]]:  
        if '>=' in spec:  
            name, version = spec.split('>=', 1)  
            return name.strip(), f">={version.strip()}"  
        elif '==' in spec:  
            name, version = spec.split('==', 1)  
            return name.strip(), f"=={version.strip()}"  
        return spec.strip(), None  
    
    def to_intermediate(self) -> Dict[str, Any]:  
        ir = {
            "name": self.config.get("name", "mb-workspace"),
            "version": self.config.get("version", "0.1.0"),
            "description": self.config.get("description", ""),
            "readme": self.config.get("readme"),
            "requires-python": self.config.get("requires-python"),
            "urls": self.config.get("urls", {}),
            "scripts": self.config.get("scripts", {}),
            "dependencies": [],
            "environment": {},
        }  
        # Add build system requirements
        build_system = self.config.get("build-system", {})
        ir["build_requires"] = build_system.get("requires", ["setuptools", "wheel"])
        ir["build_backend"] = build_system.get("build-backend", "setuptools.build_meta")
        
        for dep_str in self.config.get('deps', []):  
            dep = self._parse_dependency(dep_str)  
            dep_info = {  
                "name": dep.spec,  
                "type": "pypi",  
                "conditions": self._parse_conditions(dep.conditions)  
            }  
            if dep.is_system:  
                dep_info["type"] = "system"  
            elif dep.repo:  
                dep_info["type"] = "github"  
                dep_info["repository"] = dep.repo  
            elif dep.path:  
                dep_info["type"] = "local"  
                dep_info["path"] = str(dep.path)  
            else:  
                name, version = self._split_version(dep.spec)  
                dep_info["name"] = name  
                if version:  
                    dep_info["version"] = version  
            ir["dependencies"].append(dep_info)  
        
        self.parse_env_vars()  
        ir["environment"] = self.env_vars  
        
        return ir  
    
    def generate_nix(self, ir: dict) -> str:
        name = ir.get("name", "mb-workspace")
        description = ir.get("description") or name

        python_deps = [d for d in ir.get("dependencies", []) if d["type"] == "pypi"]
        system_deps = [d for d in ir.get("dependencies", []) if d["type"] == "system"]
        
        python_deps_str = "\n                ".join([
            f"ps.{d['name']}" for d in python_deps
        ]) or "# No Python dependencies"
        
        system_deps_str = "\n                ".join([
            f"pkgs.{d['name']}" for d in system_deps
        ]) or "# No System dependencies"

        env_vars = ir.get("environment", {})
        env_exports = "\n    ".join([
            f'export {k}="{v}"' if v else f'export {k}="${k}"'
            for k, v in env_vars.items()
        ])

        return f'''{{
        description = "{description}";

        inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
        inputs.flake-utils.url = "github:numtide/flake-utils";

        outputs = {{ self, nixpkgs, flake-utils }}:
            flake-utils.lib.eachDefaultSystem (system:
            let
                pkgs = import nixpkgs {{ inherit system; }};
                pythonEnv = pkgs.python3.withPackages (ps: [
                    {python_deps_str}
                ]);
            in
            {{
                devShell = pkgs.mkShell {{
                    buildInputs = [
                        pythonEnv
                        {system_deps_str}
                    ];
                    
                    shellHook = ''
    {env_exports}
                    '';
                }};
            }}
            );
        }}
        '''
    def convert(self) -> str:  
        ir = self.to_intermediate()  
        return self.generate_nix(ir)