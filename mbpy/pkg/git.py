from __future__ import annotations

import asyncio
import dataclasses
import logging
import os
import re
import shlex
import subprocess
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Iterable,
    Protocol,
    Set,
)

from mbpy.cmd import arun
from mbpy.helpers._cache import acache
from mbpy.import_utils import smart_import

if TYPE_CHECKING:
    from mbpy.collect import PathLike

class PackageInfo(Protocol):
    name: str
    github_url: str
    updated_at: str | None

class GitError(Exception):
    pass

log = logging.getLogger(__name__)

REF_TAG_RE = re.compile(r"(?<=\btag: )([^,]+)\b")
DESCRIBE_UNSUPPORTED = "%(describe"

# If testing command in shell make sure to quote the match argument like
# '*[0-9]*' as it will expand before being sent to git if there are any matching
# files in current directory.
DEFAULT_DESCRIBE = [
    "git",
    "describe",
    "--dirty",
    "--tags",
    "--long",
    "--match",
    "*[0-9]*",
]

if TYPE_CHECKING:
    import json as orjson
    from typing import AsyncGenerator, Protocol

    from mbpy.cmd import arun
    from mbpy.collect import Path, PathLike, PathType
    from mbpy.helpers._display import getconsole
    console = getconsole()


async def run_git(
    args: "Iterable[str | PathLike]",
    repo: "Path | str | None" = None,
    *,
    check: bool = False,
    timeout: int | None = None,  # noqa: ASYNC109
):
    if repo is not None:
        PathLike = smart_import("mbpy.collect.PathLike")
        repo = str(
            Path(repo).
            with_suffix(".git") if not str(repo).endswith(".git") else repo)

    # Execute git command
    proc = await asyncio.create_subprocess_exec(
        "git",
        *(["--git-dir", repo] if repo else []),
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(),
                                                timeout=timeout)
    except asyncio.TimeoutError:
        import traceback
        traceback.print_exc()
        proc.kill()
        await proc.wait()
        raise

    stdout_str = stdout.decode()
    stderr_str = stderr.decode()

    # Check for embedded repo warning
    if "adding embedded git repository:" in stderr_str:
        # Extract repo name from warning message
        embedded_repo = stderr_str.split(
            "adding embedded git repository:")[1].split()[0]
        # Remove from git index
        await asyncio.create_subprocess_exec("git",
                                             "rm",
                                             "--cached",
                                             embedded_repo,
                                             stdout=asyncio.subprocess.PIPE,
                                             stderr=asyncio.subprocess.PIPE)
        # Return early with error
        return ((stdout_str,
                 f"Removed embedded repository {embedded_repo} from index"),
                -1)

    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode,
                                            args,
                                            output=stdout,
                                            stderr=stderr)

    return ((stdout_str, stderr_str), proc.returncode)


async def push(remote: "Path", *, timeout: int | None = None, branch: str | None = "main") -> None:
    """Push changes to remote repository with robust conflict handling."""
    console = smart_import("mbpy.helpers._display.getconsole")()
    remote = Path(str(remote))
    # Store original branch for recovery
    original_branch, _ = await run_git(["rev-parse", "--abbrev-ref", "HEAD"], timeout=timeout)
    original_branch = original_branch[0].strip()
    
    try:
        if branch is None:
            branch = "main"

        # Format remote URL
        remote_url = str(remote)
        if not remote_url.startswith(("https://", "git@")):
            if "/" in remote_url:
                remote_url = f"https://github.com/{remote_url}"
            else:
                results, _ = await run_git(["config", "--get", "user.name"], timeout=timeout)
                username = results[0].strip() or "origin"
                remote_url = f"https://github.com/{username}/{remote_url}"

        # Setup remote if needed
        check_origin, _ = await run_git(["remote"], timeout=timeout)
        if "origin" not in check_origin[0]:
            console.print(f"Adding remote origin: {remote_url}")
            await run_git(["remote", "add", "origin", remote_url], timeout=timeout)
        else:
            await run_git(["remote", "set-url", "origin", remote_url], timeout=timeout)

        # Fetch all remote changes
        console.print("Fetching remote state...")
        await run_git(["fetch", "--all"], timeout=timeout)

        # Check if branch exists remotely
        remote_exists, _ = await run_git(["ls-remote", "--heads", "origin", branch], timeout=timeout)
        branch_exists = bool(remote_exists[0].strip())

        if branch_exists:
            # If branch exists remotely, try to set up tracking
            await run_git(["branch", "--set-upstream-to", f"origin/{branch}", branch], timeout=timeout, check=False)
            
            # Try to integrate remote changes
            console.print("Integrating remote changes...")
            await run_git(["pull", "--rebase", "origin", branch], timeout=timeout, check=False)
        else:
            # Create new branch if it doesn't exist
            console.print(f"Creating new branch: {branch}")
            await run_git(["checkout", "-b", branch], timeout=timeout)

        # Add changes
        console.print("Adding changes...")
        await run_git(["add", "."], timeout=timeout)

        # Initial commit with "Update" message
        console.print("Creating initial commit...")
        await run_git(["commit", "-m", "Update"], timeout=timeout, check=False)

        # Generate and amend with changelog
        generate_changelog = smart_import("mbpy.helpers.gcliff.generate_changelog")
        cl = await generate_changelog()
        console.print("Amending commit with changelog...")
        await run_git(["commit", "--amend", "-m", cl], timeout=timeout, check=False)

        # Force push with lease for safety
        console.print("Pushing changes...")
        push_result, returncode = await run_git(["push", "--force-with-lease", "origin", branch], timeout=timeout, check=False)
        
        if returncode != 0:
            if "non-fast-forward" in push_result[1]:
                # Handle non-fast-forward by creating new branch
                import time
                new_branch = f"{branch}-{int(time.time())}"
                console.print(f"Creating new branch {new_branch} for changes...")
                await run_git(["checkout", "-b", new_branch], timeout=timeout)
                await run_git(["push", "-u", "origin", new_branch], timeout=timeout)
                console.print(f"[green]Changes pushed to new branch: {new_branch}[/green]")
            else:
                raise GitError(f"Push failed: {push_result[1]}")
        else:
            console.print("[green]Changes pushed successfully[/green]")

    except Exception as e:
        console.print(f"[red]Error during push: {str(e)}[/red]")
        # Try to recover to original state
        await recover_branch(original_branch, timeout=timeout)
        raise

    finally:
        # Clean up any stashes or temporary states
        await run_git(["reset", "--hard", "HEAD"], timeout=timeout, check=False)


async def sync(repo: "Path", *, timeout: int | None = None) -> None:
    """Synchronize a git repository with its remote origin.
    
    Args:
        repo: Path to the repository
        timeout: Command timeout in seconds
    
    Raises:
        GitError: If git operations fail
    """
    if not TYPE_CHECKING:
        console = smart_import("mbpy.helpers._display.getconsole")()

    # Validate repo exists
    if not repo.exists():
        raise ValueError(f"Repository path does not exist: {repo}")

    # Check origin
    out, returncode = await run_git(["remote", "get-url", "origin"],
                                               repo,
                                               timeout=timeout)
    
    stdout, stderr = out

    if returncode != 0 and not stdout:
        # Extract org/repo from repo path
        repo_name = repo.name
        repo_org = repo.parent.name
        console.print(f"Adding remote origin for {repo_org}/{repo_name}")
        _, _, returncode = await run_git([
            "remote", "add", "origin",
            f"https://github.com/{repo_org}/{repo_name}"
        ],
                                         repo,
                                         timeout=timeout)
        if returncode != 0:
            raise GitError("Failed to add remote origin")

    # Pull changes
    results, returncode = await run_git(["pull", "--ff-only"],
                                        repo,
                                        timeout=timeout)
    if returncode != 0:
        if "embedded git repository" in results[1]:
            console.print(
                "[yellow]Warning: Embedded git repository detected[/]")
            # Handle embedded repo case - could add submodule or remove cached
            return
        raise GitError(f"Pull failed: {results[1]}")

    console.print(results[0] + "\n" + results[1])

    # Fetch all branches
    console.print("Fetching all branches...")
    results, returncode = await run_git(["fetch", "--all"],
                                        repo,
                                        timeout=timeout)
    if returncode != 0:
        raise GitError(f"Fetch failed: {results[1]}")

    console.print(results[0] + "\n" + results[1])

async def undo_last_commit(repo: "Path | None | str" = None, *, timeout: int | None = None) -> None:
    console = smart_import("mbpy.helpers._display.getconsole")()
    results, returncode = await run_git(["reset", "--soft", "HEAD~1"], repo, timeout=timeout)
    console.print(results[0] + "\n" + results[1])
    
    # Use run_git instead of arun for git commands
    results, _ = await run_git(["status"], repo, timeout=timeout)
    console.print(results[0] + "\n" + results[1])
    
    results, _ = await run_git(["reset"], repo, timeout=timeout)
    console.print(results[0] + "\n" + results[1])

async def suggest_similar(package: str) -> "Iterable[dict[str, str] | PackageInfo]":
    if TYPE_CHECKING:
        import json as orjson

        from rich.table import Table

        from mbpy import ctx
        from mbpy.cmd import arun
        from mbpy.helpers._display import display_similar_repos_table, getconsole
        from mbpy.pkg.dependency import org_and_repo
        from mbpy.pkg.pypi import find_and_sort
        from more_itertools import unique_everseen
        console = getconsole()
    else:
        console = smart_import("mbpy.helpers._display.getconsole")()
        find_and_sort = smart_import("mbpy.pkg.pypi.find_and_sort")
        display_similar_repos_table = smart_import("mbpy.helpers._display.display_similar_repos_table")
        arun = smart_import("mbpy.cmd.arun")
        ctx = smart_import("mbpy.ctx")
        org_and_repo = smart_import("mbpy.pkg.dependency.org_and_repo")
        unique_everseen = smart_import("more_itertools.unique_everseen")
        try:
            orjson = smart_import("orjson","lazy")
        except ImportError:
            import json as orjson
    outs = []
    async for pkg in find_and_sort(package):
        outs.append(pkg)

    org,repo = org_and_repo(package)
    out1 = str(await arun(f"gh search repos --json name --json updatedAt --json url --json stargazersCount --json description {org}/{repo}")).lower()

    out2: str = str(await arun(f"gh search repos --json name --json updatedAt --json url --json stargazersCount --json description {repo}")).lower()

    with ctx.suppress() as e:
        if out1 and "could not resolve to a repository" not in out1:
            out1 = out1[out1.find("["):out1.rfind("]")].strip()
        if out2 and "could not resolve to a repository" not in out2:
            out2 = out2[out2.find("["):out2.rfind("]")].strip()

    gh_results = []
    for out in (out1, out2):
        if out and "[" in out:
            gh_results.extend(orjson.loads(o[o.find("{"):].strip().rstrip("}") + "}") 
                            for o in out.split("},") if o and "{" in o)

    # Sort results by similarity to package name and recency
    def sort_key(item):
        name = item.get("name", "") or item.get("github_url", "").split("/")[-1]
        similarity = SequenceMatcher(None, package.lower(), name.lower()).ratio()
        updated = item.get("updatedat", "") or item.get("updated_at", "")
        return (-similarity, -len(updated))  # Negative for descending order

    combined_results = outs + gh_results
    return unique_everseen(sorted(combined_results, key=sort_key),key=sort_key)

def uv_error(line) -> bool:
    line = str(line)
    return line.lower().strip().startswith("error") or "failed" in line.lower() or "error" in line.lower() or "fatal" in line.lower() or "ERROR" in line

async def check_repo(repo:str, version=None, quiet=True):
    if TYPE_CHECKING:
        from rich.table import Table

        from mbpy import ctx
        from mbpy.cmd import arun
        from mbpy.helpers._display import display_similar_repos_table, getconsole
        console = getconsole()
    else:
        console = smart_import("mbpy.helpers._display.getconsole")()
        arun = smart_import("mbpy.cmd").arun
        ctx = smart_import("mbpy.ctx",debug=True)
        display_similar_repos_table = smart_import("mbpy.helpers._display.display_similar_repos_table")
    repo = repo.split("@")[0]
    if "==" in repo:
        repo = repo.split("==")[0]
        version = repo.split("==")[1]
    import json as orjson
    if "==" in repo:
        repo = repo.split("==")[0]
        version = repo.split("==")[1]
    if "@" in repo:
        version = repo.split("@")[1]
        repo = repo.split("@")[0]
    
    # Fix command string construction
    branch_part = f"--branch {version}" if version else ""
    out = str(await arun(f"gh repo view {repo} --json name {branch_part}", shell=True, show=not quiet)).lower()
    
    if "could not resolve to a repository" in out:
        return False
    if repo.startswith("git+"):
        repo = repo[4:]
    if not repo.startswith("https"):
        repo = f"git+https://github.com/{repo}"
    return repo

# Add tracking set for cloned repos
_cloned_repos: Set[str] = set()
_clone_locks: dict[str, asyncio.Lock] = {}

@acache
async def clone_repo(repo: str, path: "PathType")-> "AsyncGenerator[str, None]":
    """Clone repository with lock to prevent multiple clones."""

    if TYPE_CHECKING:
        from mbpy.helpers._display import getconsole
        from mbpy.cmd import arun_command
    else:
        getconsole = smart_import("mbpy.helpers._display.getconsole")
        arun_command = smart_import("mbpy.cmd.arun_command")

    if not isinstance(path, Path):
        path = Path(path)

    # Clean up repo URL and ensure org/repo format
    if repo.startswith("git+"):
        repo = repo[4:]
    
    # Ensure we have org/repo format
    if "/" not in repo and not repo.startswith(("https://", "git://", "file://")):
        # Get org from gh cli
        console = getconsole()
        try:
            orgs = (await arun("gh org list", shell=True)).strip().splitlines()
            if len(orgs) > 2:  # Account for header line
                org = orgs[-1].strip()
                repo = f"{org}/{repo}"
            else:
                raise RuntimeError("No GitHub organization found")
        except Exception as e:
            console.print(f"[red]Failed to get GitHub organization: {str(e)}[/red]")
            raise

    # Extract base repo URL before any @ symbol
    repo = repo.split('@')[0].strip()

    if not repo.startswith(("https://", "git://", "file://")):
        repo = f"https://github.com/{repo}"

    # Create unique key for repo+path combination
    clone_key = f"{repo}:{str(path)}"

    # Rest of the function remains the same...
    if clone_key in _cloned_repos:
        return

    if clone_key not in _clone_locks:
        _clone_locks[clone_key] = asyncio.Lock()

    async with _clone_locks[clone_key]:
        if clone_key in _cloned_repos:
            return

        console = getconsole()
        console.print(f"Cloning {repo} to {path}")

        if path.exists():
            import shutil
            shutil.rmtree(path)

        try:
            # Use run_git instead of arun_command for git operations
            results, returncode = await run_git(["clone", repo, str(path)])
            if returncode != 0:
                import inspect
                caller_file_line = f"{inspect.currentframe().f_back.f_code.co_filename}:{inspect.currentframe().f_back.f_lineno}"
                raise RuntimeError(f"Git clone failed: {results[1]} ({caller_file_line})")
                
            _cloned_repos.add(clone_key)
            console.print(f"Clone completed for {repo}")
            yield results[0]

        except Exception as e:
            import traceback
            traceback.print_exc()
            console.print(f"[red]Failed to clone {repo}: {str(e)}[/red]")
            raise


async def repo_exists(repo, version=None):
    return await check_repo(repo,version)

async def purge_submodules(*, timeout: int | None = None) -> None:
    """Remove all submodules with confirmation."""
    console = smart_import("mbpy.helpers._display.getconsole")()
    
    # Get list of submodules
    results, _ = await run_git(["submodule", "status"], timeout=timeout)
    if not results[0].strip():
        return

    submodules = [line.split()[1] for line in results[0].splitlines()]
    
    if not submodules:
        return
        
    console.print("[yellow]Found submodules that should be removed:[/yellow]")
    for submodule in submodules:
        console.print(f"  - {submodule}")
    
    # Use rich prompt instead of shell command
    from rich.prompt import Confirm
    if Confirm.ask("Do you want to remove these submodules?"):
        for submodule in submodules:
            console.print(f"Removing submodule: {submodule}")
            # Remove from .git/config
            await run_git(["submodule", "deinit", "-f", submodule], timeout=timeout)
            # Remove from .git/modules
            await run_git(["rm", "-f", submodule], timeout=timeout)
            # Remove directory
            if (Path(submodule)).exists():
                import shutil
                shutil.rmtree(submodule)
        # Remove .gitmodules if it exists
        if Path(".gitmodules").exists():
            Path(".gitmodules").unlink()
        console.print("[green]Submodules removed successfully[/green]")

async def recover_branch(branch: str | None = None, *, timeout: int | None = None) -> None:
    """Recover from a failed rebase and return to original branch."""
    console = smart_import("mbpy.helpers._display.getconsole")()
    
    # Get current branch if none specified
    if not branch:
        results, _ = await run_git(["rev-parse", "--abbrev-ref", "HEAD"], timeout=timeout)
        branch = results[0].strip()
    
    try:
        # Stash any untracked files first
        await run_git(["stash", "push", "--include-untracked"], timeout=timeout)
        
        # Try to abort any in-progress rebase
        try:
            await run_git(["rebase", "--abort"], timeout=timeout)
        except Exception:
            pass
        
        # Force checkout the original branch
        await run_git(["checkout", "-f", branch], timeout=timeout)
        
        # Try to restore stashed changes
        stash_results, _ = await run_git(["stash", "list"], timeout=timeout)
        if stash_results[0].strip():
            await run_git(["stash", "pop"], timeout=timeout)
            
        console.print(f"[green]Successfully recovered to branch: {branch}[/green]")
        
    except Exception as e:
        console.print(f"[red]Failed to recover normally, attempting hard recovery: {str(e)}[/red]")
        try:
            # Nuclear option - reset everything and force checkout
            await run_git(["reset", "--hard"], timeout=timeout)
            await run_git(["clean", "-fd"], timeout=timeout)
            await run_git(["checkout", "-f", branch], timeout=timeout)
        except Exception as e2:
            console.print(f"[red]Hard recovery also failed: {str(e2)}[/red]")
            raise
