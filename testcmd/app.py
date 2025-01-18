import asyncio
import cProfile
import json
import os
import platform
import pstats
import re
import shutil
import subprocess
import sys
import traceback
from asyncio.log import logger
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from itertools import chain
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

# Type Checking and Linting
import mypy.api

# Advanced Dependency Management
import rich_click as click

# Security Scanning
from Cython.Build import cythonize
from packaging import version

# Map terminal colors to their exact hex values
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn
from rich.prompt import Confirm
from rich.style import Style

# Map your terminal's ANSI escape codes to `rich` styles
from rich.theme import Theme

# Build System Enhanced
from setuptools.command.build_ext import build_ext

# Create a console with the custom theme
console = Console(style="bold light_goldenrod2")




class CythonSourceAnalyzer:
    """Advanced source code analyzer for Cython projects.

    Detects optimizable sections, type hints, and compilation opportunities
    """

    @staticmethod
    def analyze_cython_files(project_path: Path) -> Dict:
        """Comprehensive analysis of Cython source files.

        Detects:
        - Potential type optimizations
        - Nogil sections
        - Inline candidates
        - Performance bottlenecks
        """
        analysis_results = {"files": {}, "global_recommendations": []}

        cython_files = list(project_path.rglob("*.pyx")) + list(project_path.rglob("*.pxd"))

        for file in cython_files:
            with Path(file).open("r") as f:
                content = f.read()
                file_analysis = CythonSourceAnalyzer._analyze_single_file(content)
                analysis_results["files"][str(file)] = file_analysis

        return analysis_results

    @staticmethod
    def _analyze_single_file(source_code: str) -> Dict:
        """Detailed single file analysis."""
        recommendations = []

        # Type inference detection
        if "cdef" not in source_code:
            recommendations.append("Consider adding type declarations")

        # Nogil section detection
        if "with nogil:" not in source_code:
            recommendations.append("Check for nogil opportunities in compute-heavy sections")

        # Inline function candidates
        inline_candidates = [line for line in source_code.splitlines() if "def " in line and len(line.split()) < 20]

        return {"recommendations": recommendations, "inline_candidates": inline_candidates}


@dataclass
class CompilationFlagConfig:
    """Comprehensive configuration for compilation optimization.

    Provides a flexible, research-backed approach to generating
    compiler optimization flags based on:
    - CPU Architecture
    - Computational Use Case
    - Performance vs Safety Trade-offs
    - Platform Specifics

    Attributes:
        architecture (str): Target CPU architecture (x86_64, arm64, etc.)
        use_case (Literal): Optimization strategy for specific workloads
        safety_level (int): Balance between optimization and code safety
        debug (bool): Enable additional debugging information

    Example:
        >>> config = CompilationFlagConfig(
        ...     architecture='x86_64',
        ...     use_case='scientific',
        ...     safety_level=2
        ... )
        >>> flags = config.generate_flags()
    """

    architecture: str = field(default_factory=platform.machine)
    use_case: Literal["general", "scientific", "machine_learning", "high_performance", "embedded"] = "general"
    safety_level: int = 1  # 0: Aggressive, 3: Most Conservative
    debug: bool = False

    def _detect_cpu_features(self) -> Dict[str, bool]:
        """Detect advanced CPU features using platform-specific methods.

        Returns:
            Dict of available CPU features (AVX, SSE, NEON, etc.)
        """
        try:
            # Linux-based CPU feature detection
            if sys.platform.startswith("linux"):
                cpuinfo = Path("/proc/cpuinfo").read_text()

                return  {
                    "avx2": "avx2" in cpuinfo.lower(),
                    "avx512": "avx-512" in cpuinfo.lower(),
                    "sse4_2": "sse4_2" in cpuinfo.lower(),
                    "neon": "neon" in cpuinfo.lower(),
                }


            # Fallback for other platforms
            return {"avx2": False, "avx512": False, "sse4_2": False, "neon": False}
        except Exception:
            return {}

    def generate_flags(self) -> Dict[str, List[str]]:
        """Generate comprehensive compilation flags.

        Dynamically creates optimization flags based on:
        - CPU architecture
        - Computational use case
        - Available CPU features
        - Safety constraints

        Returns:
            Dictionary of compilation flags for different stages
        """
        cpu_features = self._detect_cpu_features()

        # Base optimization strategy matrix
        optimization_strategies = {
            "general": {"flags": ["-O2", "-march=native", "-mtune=native"], "safety_adjustment": ["-Wall", "-Wextra"]},
            "scientific": {
                "flags": ["-Ofast", "-ffast-math", "-ftree-vectorize", "-fopenmp"],
                "safety_adjustment": ["-Werror=float-conversion"],
            },
            "machine_learning": {
                "flags": ["-O3", "-march=native", "-funroll-loops", "-ftree-parallelize-loops=4"],
                "safety_adjustment": ["-Wno-unused-parameter"],
            },
            "high_performance": {
                "flags": ["-O3", "-funroll-all-loops", "-finline-functions", "-fomit-frame-pointer"],
                "safety_adjustment": [],
            },
            "embedded": {
                "flags": [
                    "-Os",  # Optimize for size
                    "-ffunction-sections",
                    "-fdata-sections",
                ],
                "safety_adjustment": ["-Wall"],
            },
        }

        # Architecture-specific extensions
        arch_extensions = {
            "x86_64": {"avx2": ["-mavx2", "-mfma"], "avx512": ["-mavx512f", "-mavx512er"], "sse4_2": ["-msse4.2"]},
            "arm64": {"neon": ["-mfpu=neon-fp-armv8", "-mfloat-abi=hard"]},
        }

        # Select base strategy
        base_strategy = optimization_strategies.get(self.use_case, optimization_strategies["general"])

        # Compile flags
        compilation_flags = {
            "compiler_flags": base_strategy["flags"].copy(),
            "warning_flags": base_strategy["safety_adjustment"].copy(),
            "debug_flags": [],
        }

        # Add architecture-specific optimizations
        if self.architecture in arch_extensions:
            for feature, ext_flags in arch_extensions[self.architecture].items():
                if cpu_features.get(feature, False):
                    compilation_flags["compiler_flags"].extend(ext_flags)

        # Safety level adjustments
        safety_levels = {
            0: [],  # Aggressive
            1: ["-Wall"],  # Standard warnings
            2: ["-Wall", "-Wextra", "-Wpedantic"],  # Comprehensive
            3: ["-Wall", "-Wextra", "-Wpedantic", "-Werror"],  # Most conservative
        }

        compilation_flags["warning_flags"].extend(safety_levels.get(self.safety_level, []))

        # Debug flag handling
        if self.debug:
            compilation_flags["debug_flags"] = [
                "-g",  # Generate debug information
                "-fno-omit-frame-pointer",
                "-fno-inline",
            ]

        return compilation_flags

 


def optimize_cython_build(use_case: str = "high_performance", safety_level: int = 1) -> Dict[str, List[str]]:
    """High-level function to get optimized compilation flags.

    Args:
        use_case: Optimization strategy
        safety_level: Code safety vs performance trade-off

    Returns:
        Compilation flags dictionary
    """
    config = CompilationFlagConfig(
        use_case=use_case,  # type: ignore
        safety_level=safety_level,
    )
    return config.generate_flags()

def is_third_party(path: Path) -> bool:
    """Check if a file is from a third-party package."""
    return ".venv" in str(path) or "site-packages" in str(path) or "venv" in str(path)
def has_py(path: Path) -> bool:
    """Check if a file has a corresponding .py file."""
    return path.with_suffix(".py").exists() or path.with_suffix(".pyx").exists()


class StreamHandler:
    """Custom stream handler to process stdout and stderr in real time."""

    def __init__(self, process_line_callback, original_stream):
        self.process_line_callback = process_line_callback
        self.buffer = ""
        self.original_stream = original_stream

    def write(self, data):
        self.buffer += data
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            self.process_line_callback(line)

    def flush(self):
        if self.buffer:
            self.process_line_callback(self.buffer)
            self.buffer = ""
class UltimateCythonManager:
    def __init__(self, project_path: Path = Path("mbpy")):
        self.project_path = project_path.absolute()
        self.build_cache = self.project_path / ".cython_builds"
        self.metadata_file = self.build_cache / "builds.json"
        self.console = Console()
        self.cython_enabled = True
    

    
    async def _compile_cython(
        self,
        optimization_flags: List[str],
        compiler_flags: List[str],
        use_case: str,
        nthreads: int,
        verbose: bool,
        force: bool,
    ):
        """Compile Cython extensions with the given flags."""
        cython_files = (
            list(self.project_path.glob("**/*.pyx"))
            + list(self.project_path.glob("**/*.pxd"))
            + list(self.project_path.glob("**/*.py"))
        )
        from rich.pretty import pprint
        flags = {"compiler_flags": compiler_flags + optimization_flags}
        opt_flags = optimize_cython_build(use_case=use_case)
        console = Console(stderr=True,force_terminal=True)
    
        if not cython_files:
            console.print("[yellow]No Cython files found![/yellow]")


        cython_files = [str(file) for file in cython_files if "cython" not in str(file) and not ".venv" in str(file)]
        print(cython_files)
       
        cythonize(
            cython_files,
            compiler_directives={"language_level": "3", "boundscheck": False, "wraparound": True},
            compile_time_env={"COMPILER_FLAGS": flags["compiler_flags"]},
            nthreads=nthreads,
            quiet=not verbose,
            force=force,
        )
    async def build(
            self,
            use_case: str = "high_performance",
            nthreads: int = 4,
            verbose: bool = False,
            gpu_acceleration: bool = False,
            profile: bool = False,
            optimization_level: str = "aggressive",
            force: bool = True,
        ):
            """Advanced Cython build with multiple optimization strategies."""
            errors = []
            progress = Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("{task.completed}"),
                transient=True,
            )
            original_stdout = sys.__stdout__
            original_stderr = sys.__stderr__

        
            # Profiling setup
            profiler = cProfile.Profile() if profile else None
            if profiler:
                profiler.enable()

            opt_flags = optimize_cython_build(use_case=use_case)
            stdout_console = Console(file=original_stdout, force_terminal=True)
            stderr_console = Console(file=original_stderr, force_terminal=True)
            from rich.pretty import pprint

            with progress:
                task = progress.add_task("Building Cython Extensions...", total=None)

                # Define callbacks for stdout and stderr
                def process_stdout(line: str):
                    stdout_console.print(f"[grey]{line}[/grey]")
                    if "Cythonizing" in line:
                        progress.advance(task)

                def process_stderr(line: str):
                    error_match = re.match(r"^(.*?):(\d+):(\d+):\s*(.*)", line)
                    if error_match:
                        file_path, line_num, column_num, message = error_match.groups()
                        error_message = f"{file_path}:{line_num}:{column_num}: {message}"
                        errors.append(error_message)
                        file_path = str(Path(file_path).expanduser().absolute())
                        stderr_console.print(f"[link='file://{file_path}:{line_num}'][red]{error_message}[/red][/link]")
                    else:
                        stderr_console.print(f"[yellow]{line}[/yellow]")

            # Initialize custom stream handlers with correct original streams
            stdout_handler = StreamHandler(process_stdout, original_stdout)
            stderr_handler = StreamHandler(process_stderr, original_stderr)
             # Compilation flag detection
            compilation_config = self._detect_compilation_flags()

            # Optimization strategies
            opt_strategies = {
                "standard": ["-O2"],
                "aggressive": ["-O3", "-march=native"],
                "debug": ["-O0", "-g"],
            }
            # Capture stdout and stderr
            try:
                with redirect_stdout(stdout_handler), redirect_stderr(stderr_handler):
                    await self._compile_cython(
                        compiler_flags=compilation_config["compiler_flags"],
                        optimization_flags=opt_strategies[optimization_level],
                        use_case=use_case,
                        nthreads=nthreads,
                        verbose=verbose,
                        force=force,
                    )
            except Exception as e:
                errors.append(str(e))
                stderr_console.print(f"[red]Exception occurred: {e}[/red]")
                import traceback
                traceback.print_exc(file=original_stderr)

            # Finalize progress
            progress.update(task, completed=1)
            progress.stop()

            if profiler:
                profiler.disable()

            if errors:
                stderr_console.print("[red]Build Failed with the following errors:[/red]")
                for error in errors:
                    stderr_console.print(f"[red]{error}[/red]")
            else:
                stdout_console.print("[green]Build succeeded without errors.[/green]")

            # Move .c and .so files to install directory
            install_dir = self.project_path / "src"
            Path(install_dir).mkdir(exist_ok=True, parents=True)
            for item in set(chain(self.project_path.glob("**/*.c"), self.project_path.glob("**/*.so"))):
                try:
                    if is_third_party(item) or not has_py(item):
                        continue
                    shutil.move(str(item), install_dir / item.name)
                except shutil.Error as e:
                    stderr_console.print(f"[red]Failed to move {item}: {e}[/red]")
            await self.buildext()
            return True
        
    def _detect_compilation_flags(self,system=None, machine=None) -> Dict:
        """Detect optimal compilation flags based on system."""
        system = system or platform.system()
        machine = machine or platform.machine()

        flags = {
            "common": ["-O3", "-march=native"],
            "Linux": ["-fPIC", "-fopenmp"],
            "Darwin": ["-fPIC", "-Xpreprocessor", "-fopenmp"],
            "Windows": ["/openmp", "/O2"],
        }

        # SIMD and platform-specific optimizations
        simd_flags = {"x86_64": ["-mavx2", "-mfma"], "arm64": ["-march=armv8-a+fp+simd"]}

        compilation_flags = flags.get(system, []) + simd_flags.get(machine, [])
        return {"compiler_flags": compilation_flags, "system": system, "architecture": machine}

  

    async def _run_type_checks(self):
        """Comprehensive static type checking."""
        try:
            result, _, _ = mypy.api.run(["--ignore-missing-imports", "--strict", str(self.project_path / "src")])
            self.console.print("[blue]Type Check Results:[/blue]")
            self.console.print(result)
        except Exception as e:
            self.console.print(f"[red]Type check failed: {e}. Did you install mypy?[/red]")
    

    

    
    async def clean(self, force: bool = False) -> bool:
        """Clean build artifacts and temporary files.
        
        Args:
            force: Skip confirmation
        
        Returns:
            Cleaning success status
        """
        paths_to_clean = [
            self.project_path / 'build',
            self.project_path / 'install',
            self.project_path / 'dist',
            self.project_path / '*.egg-info',
            self.project_path.glob('**/*.pyc'),
            self.project_path.glob('**/*.so'),
            self.project_path.glob('**/*.c'),
            self.project_path.glob('src/**/*.egg-info'),
            self.project_path.glob('src/**/*.c'),
            self.project_path.glob('src/**/*.so'),
            self.project_path.glob('src/**/*.pyc'),
        ]
        if not force:
            confirm = Confirm.ask(
                "[yellow]Do you want to clean build artifacts?", 
                default=False
            )
            if not confirm:
                return False
    
        for path in paths_to_clean:
            if isinstance(path, Path):
                if is_third_party(path) or not has_py(path):
                    continue
                shutil.rmtree(path)
            else:
                for p in path:
                    if p.exists() and not is_third_party(p) and has_py(p):
                        if p.is_file():
                            p.unlink()
                        elif p.is_dir():
                            shutil.rmtree(p)
        self.console.print("✓ Build artifacts cleaned")
        return True
    
    async def toggle_cython(self):  
        """Toggle between Cython and pure Python."""  
        self.cython_enabled = not self.cython_enabled  
        await self.update_active_version()  
        print(f"Cython mode is now {'enabled' if self.cython_enabled else 'disabled'}.")  

    async def update_active_version(self):  
        """Update the active version symlink."""  
        target = "mod.cpython-311-darwin.so" if self.cython_enabled else "mod.py"  
        active_link = os.path.join(self.project_path, "src", "active_version") 
        cython_files = [file for file in os.listdir(self.project_path / "src") if file.endswith(".pyx")]  
        
        if self.cython_enabled:  
            for cython_file in cython_files:  
                pyx_path = os.path.join(self.project_path, "src", cython_file)  
                print(f"Compiling {pyx_path}...")  

                self.asubprocess = await asyncio.create_subprocess_exec(
                sys.executable,*[ "-m", "Cython", str(pyx_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
        # Remove existing symlink if it exists  
        if Path(active_link).is_symlink():
            Path(active_link).unlink()

        # Create a new symlink to the active module  
        if self.cython_enabled:  
            symlink_target = self.project_path / "build", target
            os.symlink(str(symlink_target), active_link)  
        else:  
            # Pointing to the pure Python file for a non-build mode  
            symlink_target = self.project_path / "src", target 
            os.symlink(str(symlink_target), active_link)  

        console.print(f"Active version updated to {target}.")  

    async def buildext(self):  
        """Build the Cython project."""  
        console.print(f"Building {'with Cython' if self.cython_enabled else 'without Cython'}...")  

        cython_files = [file for file in os.listdir(self.project_path / "src") if file.endswith(".pyx")]  
        
        if self.cython_enabled:  
            for cython_file in cython_files:  
                pyx_path = os.path.join(self.project_path, "src", cython_file)  
                console.print(f"Compiling {pyx_path}...")  


        console.print("Building project...")  
        self.asubprocess = await asyncio.create_subprocess_exec(
                sys.executable,*["-m", "setuptools", "build_ext", "--inplace", "--build-lib", str(self.project_path / "build")], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True
                )
        stdout, stderr = await self.asubprocess.communicate()
        await self.update_active_version()  # Update the symlink after building  
        console.print("Build completed successfully.")  

   
# CLI Implementation with Rich and Click
@click.group()
@click.option('--project-path', type=click.Path(exists=True), help='Project root directory')
@click.option('--config',default="pyproject.toml",type=click.Path(exists=True), help='Configuration file path')
@click.pass_context
def cli(ctx, project_path, config):
    """Comprehensive Cython Package Management CLI.
    
    Advanced build, optimization, and management tools
    """
    ctx.ensure_object(dict)
    ctx.obj['manager'] = UltimateCythonManager(
        project_path=Path(project_path) if project_path else Path("mbpy")
    )

@cli.command()
@click.option('--version', help='Specific version to build')
@click.option('--optimized/--no-optimized', default=False, help='Apply performance optimizations')
@click.option('--debug/--no-debug', default=False, help='Enable debug build')
@click.pass_context
def build(ctx, version, optimized, debug):
    """Build Cython package with advanced options."""
    manager: UltimateCythonManager = ctx.obj['manager']
    success = asyncio.run(manager.build("high_performance" if optimized else "general"))
    sys.exit(0 if success else 1)


@cli.command()
@click.pass_context
@click.argument("on_off",type=click.Choice(["on", "off"]))
def cython(ctx, on_off):
    """Build Cython package with advanced options."""
    manager: UltimateCythonManager = ctx.obj["manager"]
    manager.cython_enabled = on_off == "on"
    success = asyncio.run(manager.update_active_version())
    sys.exit(0 if success else 1)


@cli.command()
@click.option('--force', '-f', is_flag=True, help='Skip confirmation')
@click.pass_context
def clean(ctx, force):
    """Clean build artifacts and temporary files."""
    manager: UltimateCythonManager = ctx.obj['manager']
    success = asyncio.run(manager.clean(force))
      

def main():
    cli(obj={})

if __name__ == '__main__':
    main()


