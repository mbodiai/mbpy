from __future__ import annotations

import ast
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List

from Cython.Build import cythonize
from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from mypy import stubgen

log = logging.getLogger(__name__)



log = logging.getLogger(__name__)

@dataclass
class CythonBuildConfig:
    source_dir: str = "src"
    build_dir: str = "build"
    install_dir: str = "/usr/local/lib"
    include_patterns: List[str] = None
    exclude_patterns: List[str] = None

class CythonizeHook(BuildHookInterface):
    PLUGIN_NAME = "auto-cythonize"
    
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        config = CythonBuildConfig(**self.config)
        source_path = Path(self.root) / config.source_dir
        build_path = Path(self.root) / config.build_dir
        
        # Generate stubs for type information
        stubgen.main(['--output', str(build_path), str(source_path)])
        
        # Process each Python file
        for py_file in source_path.glob('**/*.py'):
            if not self._should_process_file(py_file, config):
                continue
                
            # Convert to Cython
            cy_file = build_path / py_file.relative_to(source_path).with_suffix('.pyx')
            cy_file.parent.mkdir(parents=True, exist_ok=True)
            
            self._convert_to_cython(py_file, cy_file)
            
        # Cythonize all generated files
        cythonize(str(build_path / "*.pyx"),
                 language_level=3,
                 compiler_directives={'binding': True})

    def _should_process_file(self, file: Path, config: CythonBuildConfig) -> bool:
      """Filter files based on include/exclude patterns."""
      relative_path = str(file.relative_to(Path(self.root) / config.source_dir))
    
      # Check exclude patterns first
      if config.exclude_patterns:
          for pattern in config.exclude_patterns:
              if Path(relative_path).match(pattern):
                  log.debug(f"Excluding {file} - matched {pattern}")
                  return False
      
      # If include patterns exist, file must match at least one
      if config.include_patterns:
          return any(Path(relative_path).match(pattern) 
                    for pattern in config.include_patterns)
    
      return True

    def _convert_to_cython(self, py_file: Path, cy_file: Path) -> None:
        # Parse Python AST
        with Path(py_file).open() as f:
            tree = ast.parse(f.read())
        
        # Parse corresponding stub file for type info
        stub_file = cy_file.with_suffix('.pyi')
        stub_types = self._parse_stub_types(stub_file)
        
        # Generate Cython code with cdefs
        cy_code = self._generate_cython_code(tree, stub_types)
        
        with Path(cy_file).open('w') as f:
            f.write(cy_code)

        
    def _parse_stub_types(self, stub_file: Path) -> dict:
        """Extract type information from stub files."""
        types = {}
        if not stub_file.exists():
            log.warning(f"No stub file found at {stub_file}")
            return types
            
        try:
            with open(stub_file) as f:
                stub_tree = ast.parse(f.read())
                
            for node in ast.walk(stub_tree):
                if isinstance(node, ast.AnnAssign):
                    # Handle variable annotations
                    if isinstance(node.target, ast.Name):
                        types[node.target.id] = self._get_type_from_annotation(node.annotation)
                        
                elif isinstance(node, ast.FunctionDef):
                    # Handle function annotations
                    func_types = {
                        'return': self._get_type_from_annotation(node.returns) if node.returns else None,
                        'args': {},
                    }
                    for arg in node.args.args:
                        if arg.annotation:
                            func_types['args'][arg.arg] = self._get_type_from_annotation(arg.annotation)
                    types[node.name] = func_types
                    
                elif isinstance(node, ast.ClassDef):
                    # Handle class type information
                    class_types = {}
                    for body_node in node.body:
                        if isinstance(body_node, ast.AnnAssign):
                            if isinstance(body_node.target, ast.Name):
                                class_types[body_node.target.id] = self._get_type_from_annotation(body_node.annotation)
                    types[node.name] = class_types
                    
        except Exception as e:
            log.error(f"Error parsing stub file {stub_file}: {e}")
            return {}
            
        return types
      
    def _get_type_from_annotation(self, annotation: ast.AST) -> str:
      """Convert AST annotation to Cython type."""
      if isinstance(annotation, ast.Name):
          type_map = {
              'int': 'int',
              'float': 'double',
              'str': 'str',
              'bool': 'bint',
              'list': 'list',
              'dict': 'dict',
              'tuple': 'tuple',
          }
          return type_map.get(annotation.id, 'object')
      if isinstance(annotation, ast.Subscript):
          # Handle generic types like List[int]
          return f"typing.{self._get_type_from_annotation(annotation.value)}"
      return 'object'

    def _convert_function(self, node: ast.FunctionDef, types: dict) -> List[str]:
      """Convert Python function to Cython with type information."""
      output = []
      
      # Get function type information
      func_types = types.get(node.name, {'return': None, 'args': {}})
      
      # Build function declaration
      return_type = func_types['return'] or 'object'
      args = []
      for arg in node.args.args:
          arg_type = func_types['args'].get(arg.arg, 'object')
          args.append(f"{arg_type} {arg.arg}")
      
      # Generate cdef function
      output.append(f"    cppdef {return_type} {node.name}({', '.join(args)}):")
      
      # Convert function body
      for body_node in node.body:
          if isinstance(body_node, ast.Return):
              output.append(f"        return {ast.unparse(body_node.value)}")
          else:
              # Convert other statements
              output.append(f"        {ast.unparse(body_node)}")
      
      return output

    def _generate_cython_code(self, tree: ast.AST, types: dict) -> str:
      """Generate Cython code from Python AST with type information."""
      output = []
      
      # Add standard imports and cimports
      output.extend([
          "# cython: language_level=3",
          "# distutils: language=c++",
          "",
          "import cython",
          "from cpython cimport *",
          "",
      ])
      
      for node in ast.walk(tree):
          if isinstance(node, ast.ClassDef):
              # Generate cdef class
              class_types = types.get(node.name, {})
              output.append(f"cdef class {node.name}:")
              
              # Add class attributes with types
              for name, type_info in class_types.items():
                  output.append(f"    cdef {type_info} {name}")
                  
              # Convert methods
              for body_node in node.body:
                  if isinstance(body_node, ast.FunctionDef):
                      output.extend(self._convert_function(body_node, types))
                      
          elif isinstance(node, ast.FunctionDef):
              # Generate cdef functions
              output.extend(self._convert_function(node, types))
              
          elif isinstance(node, ast.AnnAssign):
              # Handle typed variable declarations
              if isinstance(node.target, ast.Name):
                  var_type = self._get_type_from_annotation(node.annotation)
                  output.append(f"cdef {var_type} {node.target.id}")
      
      return "\n".join(output)