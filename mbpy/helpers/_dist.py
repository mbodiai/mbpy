"""distutils.cmd

Provides the Command class, the base class for the command classes
in the distutils.command package.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path, PurePath
import re
import string
import sys
from collections.abc import Callable
from typing import Any, ClassVar, TypeVar, overload



import functools
import itertools
import platform
import sys
"""distutils.spawn

Provides the 'spawn()' function, a front-end to various platform-
specific functions for launching another program in a sub-process.
"""

from mbpy.helpers import _modified
from mbpy.helpers._typing import passnone
from mbpy import log

import os
import platform
import shutil
import subprocess
import sys
import warnings
from collections.abc import Mapping, MutableMapping
from setuptools._distutils.debug import DEBUG

if sys.platform == 'darwin':
    _syscfg_macosx_ver = None  # cache the version pulled from sysconfig
MACOSX_VERSION_VAR = 'MACOSX_DEPLOYMENT_TARGET'
import os

try:
    import zipfile
except ImportError:
    zipfile = None


try:
    from pwd import getpwnam
except ImportError:
    getpwnam = None

try:
    from grp import getgrnam
except ImportError:
    getgrnam = None



class CompileError(Exception):
    """Raised when a compile operation fails."""

class LinkError(Exception):
    """Raised when a link operation fails."""

class ExecError(Exception):
    """Raised when a compiler executable is not found."""

class PreprocessError(Exception):
    """Raised when a preprocess operation fails."""

class LibError(Exception):
    """Raised when a library operation fails."""

class PlatformError(Exception):
    """Raised for platform-specific errors."""

class ModuleError(Exception):
    """Raised when a module could not be found."""

class OptionError(Exception):
    """Raised when an option is not valid."""

class FileError(Exception):
    """Raised for file-related errors."""

class CompileFileError(FileError):
    """Raised when a file compile operation fails."""

class InternalError(Exception):
    """Raised for internal errors."""

def _debug(cmd):
    """
    Render a subprocess command differently depending on DEBUG.
    """
    return cmd if DEBUG else cmd[0]


def find_executable(executable, path=None):
    """Tries to find 'executable' in the directories listed in 'path'.

    A string listing directories separated by 'os.pathsep'; defaults to
    os.environ['PATH'].  Returns the complete filename or None if not found.
    """
    warnings.warn(
        'Use shutil.which instead of find_executable', DeprecationWarning, stacklevel=2
    )
    _, ext = os.path.splitext(executable)
    if (sys.platform == 'win32') and (ext != '.exe'):
        executable = executable + '.exe'

    if os.path.isfile(executable):
        return executable

    if path is None:
        path = os.environ.get('PATH', None)
        # bpo-35755: Don't fall through if PATH is the empty string
        if path is None:
            try:
                path = os.confstr("CS_PATH")
            except (AttributeError, ValueError):
                # os.confstr() or CS_PATH is not available
                path = os.defpath

    # PATH='' doesn't match, whereas PATH=':' looks in the current directory
    if not path:
        return None

    paths = path.split(os.pathsep)
    for p in paths:
        f = os.path.join(p, executable)
        if os.path.isfile(f):
            # the file exists, we have a shot at spawn working
            return f
    return None


def add_ext_suffix_39(vars):
    """
    Ensure vars contains 'EXT_SUFFIX'. pypa/distutils#130
    """
    import _imp

    ext_suffix = _imp.extension_suffixes()[0]
    vars.update(
        EXT_SUFFIX=ext_suffix,
        # sysconfig sets SO to match EXT_SUFFIX, so maintain
        # that expectation.
        # https://github.com/python/cpython/blob/785cc6770588de087d09e89a69110af2542be208/Lib/sysconfig.py#L671-L673
        SO=ext_suffix,
    )


needs_ext_suffix = sys.version_info < (3, 10) and platform.system() == 'Windows'
add_ext_suffix = add_ext_suffix_39 if needs_ext_suffix else lambda vars: None


# from more_itertools
class UnequalIterablesError(ValueError):
    def __init__(self, details=None):
        msg = 'Iterables have different lengths'
        if details is not None:
            msg += (': index 0 has length {}; index {} has length {}').format(*details)

        super().__init__(msg)


# from more_itertools
def _zip_equal_generator(iterables):
    _marker = object()
    for combo in itertools.zip_longest(*iterables, fillvalue=_marker):
        for val in combo:
            if val is _marker:
                raise UnequalIterablesError()
        yield combo


# from more_itertools
def _zip_equal(*iterables):
    # Check whether the iterables are all the same size.
    try:
        first_size = len(iterables[0])
        for i, it in enumerate(iterables[1:], 1):
            size = len(it)
            if size != first_size:
                raise UnequalIterablesError(details=(first_size, i, size))
        # All sizes are equal, we can use the built-in zip.
        return zip(*iterables)
    # If any one of the iterables didn't have a length, start reading
    # them until one runs out.
    except TypeError:
        return _zip_equal_generator(iterables)


zip_strict = (
    _zip_equal if sys.version_info < (3, 10) else functools.partial(zip, strict=True)
)

_CommandT = TypeVar("_CommandT", bound="Command")
"""distutils.archive_util

Utility functions for creating archive files (tarballs, zip files,
that sort of thing)."""





def get_host_platform() -> str:
    """
    Return a string that identifies the current platform. Use this
    function to distinguish platform-specific build directories and
    platform-specific built distributions.
    """

    # This function initially exposed platforms as defined in Python 3.9
    # even with older Python versions when distutils was split out.
    # Now it delegates to stdlib sysconfig.
    from sysconfig import get_platform
    return get_platform()


def get_platform():
    if os.name == 'nt':
        TARGET_TO_PLAT = {
            'x86': 'win32',
            'x64': 'win-amd64',
            'arm': 'win-arm32',
            'arm64': 'win-arm64',
        }
        target = os.environ.get('VSCMD_ARG_TGT_ARCH')
        return TARGET_TO_PLAT.get(target) or get_host_platform()
    return get_host_platform()


def _clear_cached_macosx_ver():
    """For testing only. Do not call."""
    global _syscfg_macosx_ver
    _syscfg_macosx_ver = None


def get_macosx_target_ver_from_syscfg():
    """Get the version of macOS latched in the Python interpreter configuration.
    Returns the version as a string or None if can't obtain one. Cached."""
    global _syscfg_macosx_ver
    if _syscfg_macosx_ver is None:
        from sysconfig import get_config_var

        ver =get_config_var(MACOSX_VERSION_VAR) or ''
        if ver:
            _syscfg_macosx_ver = ver
    return _syscfg_macosx_ver


def get_macosx_target_ver():
    """Return the version of macOS for which we are building.

    The target version defaults to the version in sysconfig latched at time
    the Python interpreter was built, unless overridden by an environment
    variable. If neither source has a value, then None is returned"""

    syscfg_ver = get_macosx_target_ver_from_syscfg()
    env_ver = os.environ.get(MACOSX_VERSION_VAR)

    if env_ver:
        # Validate overridden version against sysconfig version, if have both.
        # Ensure that the deployment target of the build process is not less
        # than 10.3 if the interpreter was built for 10.3 or later.  This
        # ensures extension modules are built with correct compatibility
        # values, specifically LDSHARED which can use
        # '-undefined dynamic_lookup' which only works on >= 10.3.
        if (
            syscfg_ver
            and split_version(syscfg_ver) >= [10, 3]
            and split_version(env_ver) < [10, 3]
        ):
            my_msg = (
                '$' + MACOSX_VERSION_VAR + ' mismatch: '
                f'now "{env_ver}" but "{syscfg_ver}" during configure; '
                'must use 10.3 or later'
            )
            raise PlatformError(my_msg)
        return env_ver
    return syscfg_ver


def split_version(s):
    """Convert a dot-separated string into a list of numbers for comparisons"""
    return [int(n) for n in s.split('.')]



def _inject_macos_ver(env: MutableMapping[str,str] | None) -> MutableMapping[str,str] | None:
    if platform.system() != 'Darwin':
        return env


    target_ver = str(get_macosx_target_ver())
    update = {MACOSX_VERSION_VAR: target_ver} if target_ver else {}
    return {**_resolve(env or {}), **update}


def _resolve(env: MutableMapping[str,str] | None) -> MutableMapping[str,str]:
    return os.environ if env is None else env


def spawn(cmd, search_path=True, verbose=False, dry_run=False, env=None):
    """Run another program, specified as a command list 'cmd', in a new process.

    'cmd' is just the argument list for the new process, ie.
    cmd[0] is the program to run and cmd[1:] are the rest of its arguments.
    There is no way to run a program with a name different from that of its
    executable.

    If 'search_path' is true (the default), the system's executable
    search path will be used to find the program; otherwise, cmd[0]
    must be the exact path to the executable.  If 'dry_run' is true,
    the command will not actually be run.

    Raise ExecError if running the program fails in any way; just
    return on success.
    """
    log.info(subprocess.list2cmdline(cmd))
    if dry_run:
        return

    if search_path:
        executable = shutil.which(cmd[0])
        if executable is not None:
            cmd[0] = executable

    try:
        subprocess.check_call(cmd, env=_inject_macos_ver(env))
    except OSError as exc:
        raise ExecError(
            f"command {_debug(cmd)!r} failed: {exc.args[-1]}"
        ) from exc
    except subprocess.CalledProcessError as err:
        raise ExecError(
            f"command {_debug(cmd)!r} failed with exit code {err.returncode}"
        ) from err


@passnone
def convert_path(pathname: str | os.PathLike) -> str:
    r"""
    Allow for pathlib.Path inputs, coax to a native path string.

    If None is passed, will just pass it through as
    Setuptools relies on this behavior.

    >>> convert_path(None) is None
    True

    Removes empty paths.

    >>> convert_path('foo/./bar').replace('\\', '/')
    'foo/bar'
    """
    return os.fspath(PurePath(pathname))


def change_root(new_root, pathname):
    """Return 'pathname' with 'new_root' prepended.  If 'pathname' is
    relative, this is equivalent to "os.path.join(new_root,pathname)".
    Otherwise, it requires making 'pathname' relative and then joining the
    two, which is tricky on DOS/Windows and Mac OS.
    """
    if os.name == 'posix':
        if not os.path.isabs(pathname):
            return os.path.join(new_root, pathname)
        else:
            return os.path.join(new_root, pathname[1:])

    elif os.name == 'nt':
        (drive, path) = os.path.splitdrive(pathname)
        if path[0] == os.sep:
            path = path[1:]
        return os.path.join(new_root, path)

    raise PlatformError(f"nothing known about platform '{os.name}'")


@functools.lru_cache
def check_environ():
    """Ensure that 'os.environ' has all the environment variables we
    guarantee that users can use in config files, command-line options,
    etc.  Currently this includes:
      HOME - user's home directory (Unix only)
      PLAT - description of the current platform, including hardware
             and OS (see 'get_platform()')
    """
    if os.name == 'posix' and 'HOME' not in os.environ:
        try:
            import pwd

            os.environ['HOME'] = pwd.getpwuid(os.getuid())[5]
        except (ImportError, KeyError):
            # bpo-10496: if the current user identifier doesn't exist in the
            # password database, do nothing
            pass

    if 'PLAT' not in os.environ:
        os.environ['PLAT'] = get_platform()


def subst_vars(s, local_vars):
    """
    Perform variable substitution on 'string'.
    Variables are indicated by format-style braces ("{var}").
    Variable is substituted by the value found in the 'local_vars'
    dictionary or in 'os.environ' if it's not in 'local_vars'.
    'os.environ' is first checked/augmented to guarantee that it contains
    certain values: see 'check_environ()'.  Raise ValueError for any
    variables not found in either 'local_vars' or 'os.environ'.
    """
    check_environ()
    lookup = dict(os.environ)
    lookup.update((name, str(value)) for name, value in local_vars.items())
    try:
        return _subst_compat(s).format_map(lookup)
    except KeyError as var:
        raise ValueError(f"invalid variable {var}")


def _subst_compat(s):
    """
    Replace shell/Perl-style variable substitution with
    format-style. For compatibility.
    """

    def _subst(match):
        return f'{{{match.group(1)}}}'

    repl = re.sub(r'\$([a-zA-Z_][a-zA-Z_0-9]*)', _subst, s)
    if repl != s:
        import warnings

        warnings.warn(
            "shell/Perl-style substitutions are deprecated",
            DeprecationWarning,
        )
    return repl


def grok_environment_error(exc, prefix="error: "):
    # Function kept for backward compatibility.
    # Used to try clever things with EnvironmentErrors,
    # but nowadays str(exception) produces good messages.
    return prefix + str(exc)


# Needed by 'split_quoted()'
_wordchars_re = _squote_re = _dquote_re = None


def _init_regex():
    global _wordchars_re, _squote_re, _dquote_re
    _wordchars_re = re.compile(rf'[^\\\'\"{string.whitespace} ]*')
    _squote_re = re.compile(r"'(?:[^'\\]|\\.)*'")
    _dquote_re = re.compile(r'"(?:[^"\\]|\\.)*"')


def split_quoted(s):
    """Split a string up according to Unix shell-like rules for quotes and
    backslashes.  In short: words are delimited by spaces, as long as those
    spaces are not escaped by a backslash, or inside a quoted string.
    Single and double quotes are equivalent, and the quote characters can
    be backslash-escaped.  The backslash is stripped from any two-character
    escape sequence, leaving only the escaped character.  The quote
    characters are stripped from any quoted string.  Returns a list of
    words.
    """
    import string
    # This is a nice algorithm for splitting up a single string, since it
    # doesn't require character-by-character examination.  It was a little
    # bit of a brain-bender to get it working right, though...
    if _wordchars_re is None:
        _init_regex()

    s = s.strip()
    words = []
    pos = 0

    while s:
        m = _wordchars_re.match(s, pos)
        end = m.end()
        if end == len(s):
            words.append(s[:end])
            break

        if s[end] in string.whitespace:
            # unescaped, unquoted whitespace: now
            # we definitely have a word delimiter
            words.append(s[:end])
            s = s[end:].lstrip()
            pos = 0

        elif s[end] == '\\':
            # preserve whatever is being escaped;
            # will become part of the current word
            s = s[:end] + s[end + 1 :]
            pos = end + 1

        else:
            if s[end] == "'":  # slurp singly-quoted string
                m = _squote_re.match(s, end)
            elif s[end] == '"':  # slurp doubly-quoted string
                m = _dquote_re.match(s, end)
            else:
                raise RuntimeError(f"this can't happen (bad char '{s[end]}')")

            if m is None:
                raise ValueError(f"bad string (mismatched {s[end]} quotes?)")

            (beg, end) = m.span()
            s = s[:beg] + s[beg + 1 : end - 1] + s[end:]
            pos = m.end() - 2

        if pos >= len(s):
            words.append(s)
            break

    return words


# split_quoted ()


def execute(func, args, msg=None, verbose=False, dry_run=False):
    """Perform some action that affects the outside world (eg.  by
    writing to the filesystem).  Such actions are special because they
    are disabled by the 'dry_run' flag.  This method takes care of all
    that bureaucracy for you; all you have to do is supply the
    function to call and an argument tuple for it (to embody the
    "external action" being performed), and an optional message to
    print.
    """
    if msg is None:
        msg = f"{func.__name__}{args!r}"
        if msg[-2:] == ',)':  # correct for singleton tuple
            msg = msg[0:-2] + ')'

    log.info(msg)
    if not dry_run:
        func(*args)


def strtobool(val):
    """Convert a string representation of truth to true (1) or false (0).

    True values are 'y', 'yes', 't', 'true', 'on', and '1'; false values
    are 'n', 'no', 'f', 'false', 'off', and '0'.  Raises ValueError if
    'val' is anything else.
    """
    val = val.lower()
    if val in ('y', 'yes', 't', 'true', 'on', '1'):
        return 1
    elif val in ('n', 'no', 'f', 'false', 'off', '0'):
        return 0
    else:
        raise ValueError(f"invalid truth value {val!r}")


def byte_compile(  # noqa: C901
    py_files,
    optimize=0,
    force=False,
    prefix=None,
    base_dir=None,
    verbose=True,
    dry_run=False,
    direct=None,
):
    """Byte-compile a collection of Python source files to .pyc
    files in a __pycache__ subdirectory.  'py_files' is a list
    of files to compile; any files that don't end in ".py" are silently
    skipped.  'optimize' must be one of the following:
      0 - don't optimize
      1 - normal optimization (like "python -O")
      2 - extra optimization (like "python -OO")
    If 'force' is true, all files are recompiled regardless of
    timestamps.

    The source filename encoded in each bytecode file defaults to the
    filenames listed in 'py_files'; you can modify these with 'prefix' and
    'basedir'.  'prefix' is a string that will be stripped off of each
    source filename, and 'base_dir' is a directory name that will be
    prepended (after 'prefix' is stripped).  You can supply either or both
    (or neither) of 'prefix' and 'base_dir', as you wish.

    If 'dry_run' is true, doesn't actually do anything that would
    affect the filesystem.

    Byte-compilation is either done directly in this interpreter process
    with the standard py_compile module, or indirectly by writing a
    temporary script and executing it.  Normally, you should let
    'byte_compile()' figure out to use direct compilation or not (see
    the source for details).  The 'direct' flag is used by the script
    generated in indirect mode; unless you know what you're doing, leave
    it set to None.
    """

    # nothing is done if sys.dont_write_bytecode is True
    if sys.dont_write_bytecode:
        raise CompileError('byte-compiling is disabled.')

    # First, if the caller didn't force us into direct or indirect mode,
    # figure out which mode we should be in.  We take a conservative
    # approach: choose direct mode *only* if the current interpreter is
    # in debug mode and optimize is 0.  If we're not in debug mode (-O
    # or -OO), we don't know which level of optimization this
    # interpreter is running with, so we can't do direct
    # byte-compilation and be certain that it's the right thing.  Thus,
    # always compile indirectly if the current interpreter is in either
    # optimize mode, or if either optimization level was requested by
    # the caller.
    if direct is None:
        direct = __debug__ and optimize == 0
    import tempfile
    # "Indirect" byte-compilation: write a temporary script and then
    # run it with the appropriate flags.
    if not direct:
        (script_fd, script_name) = tempfile.mkstemp(".py")
        log.info("writing byte-compilation script '%s'", script_name)
        if not dry_run:
            script = os.fdopen(script_fd, "w", encoding='utf-8')

            with script:
                script.write(
                    """\
from distutils.util import byte_compile
files = [
"""
                )

                # XXX would be nice to write absolute filenames, just for
                # safety's sake (script should be more robust in the face of
                # chdir'ing before running it).  But this requires abspath'ing
                # 'prefix' as well, and that breaks the hack in build_lib's
                # 'byte_compile()' method that carefully tacks on a trailing
                # slash (os.sep really) to make sure the prefix here is "just
                # right".  This whole prefix business is rather delicate -- the
                # problem is that it's really a directory, but I'm treating it
                # as a dumb string, so trailing slashes and so forth matter.

                script.write(",\n".join(map(repr, py_files)) + "]\n")
                script.write(
                    f"""
byte_compile(files, optimize={optimize!r}, force={force!r},
             prefix={prefix!r}, base_dir={base_dir!r},
             verbose={verbose!r}, dry_run=False,
             direct=True)
"""
                )

        cmd = [sys.executable]
        cmd.extend(subprocess._optim_args_from_interpreter_flags())
        cmd.append(script_name)
        spawn(cmd, dry_run=dry_run)
        execute(os.remove, (script_name,), f"removing {script_name}", dry_run=dry_run)

    # "Direct" byte-compilation: use the py_compile module to compile
    # right here, right now.  Note that the script generated in indirect
    # mode simply calls 'byte_compile()' in direct mode, a weird sort of
    # cross-process recursion.  Hey, it works!
    else:
        from py_compile import compile
        from ._modified import newer
        from importlib.util import cache_from_source
        for file in py_files:
            if file[-3:] != ".py":
                # This lets us be lazy and not filter filenames in
                # the "install_lib" command.
                continue

            # Terminology from the py_compile module:
            #   cfile - byte-compiled file
            #   dfile - purported source filename (same as 'file' by default)
            if optimize >= 0:
                opt = '' if optimize == 0 else optimize
                cfile = cache_from_source(file, optimization=opt)
            else:
                cfile = cache_from_source(file)
            dfile = file
            if prefix:
                if file[: len(prefix)] != prefix:
                    raise ValueError(
                        f"invalid prefix: filename {file!r} doesn't start with {prefix!r}"
                    )
                dfile = dfile[len(prefix) :]
            if base_dir:
                dfile = os.path.join(base_dir, dfile)

            cfile_base = os.path.basename(cfile)
            if direct:
                if force or newer(file, cfile):
                    log.info("byte-compiling %s to %s", file, cfile_base)
                    if not dry_run:
                        compile(file, cfile, dfile)
                else:
                    log.debug("skipping byte-compilation of %s to %s", file, cfile_base)


def rfc822_escape(header):
    """Return a version of the string escaped for inclusion in an
    RFC-822 header, by ensuring there are 8 spaces space after each newline.
    """
    indent = 8 * " "
    lines = header.splitlines(keepends=True)

    # Emulate the behaviour of `str.split`
    # (the terminal line break in `splitlines` does not result in an extra line):
    ends_in_newline = lines and lines[-1].splitlines()[0] != lines[-1]
    suffix = indent if ends_in_newline else ""

    return indent.join(lines) + suffix


def is_mingw():
    """Returns True if the current platform is mingw.

    Python compiled with Mingw-w64 has sys.platform == 'win32' and
    get_platform() starts with 'mingw'.
    """
    return sys.platform == 'win32' and get_platform().startswith('mingw')


def is_freethreaded():
    """Return True if the Python interpreter is built with free threading support."""
    import sysconfig
    return bool(sysconfig.get_config_var('Py_GIL_DISABLED'))


# for generating verbose output in 'copy_file()'
_copy_action = {None: 'copying', 'hard': 'hard linking', 'sym': 'symbolically linking'}


def _copy_file_contents(src, dst, buffer_size=16 * 1024):  # noqa: C901
    """Copy the file 'src' to 'dst'; both must be filenames.  Any error
    opening either file, reading from 'src', or writing to 'dst', raises
    FileError.  Data is read/written in chunks of 'buffer_size'
    bytes (default 16k).  No attempt is made to handle anything apart from
    regular files.
    """
    # Stolen from shutil module in the standard library, but with
    # custom error-handling added.
    fsrc = None
    fdst = None
    try:
        try:
            fsrc = open(src, 'rb')
        except OSError as e:
            raise CompileFileError(f"could not open '{src}': {e.strerror}")

        if os.path.exists(dst):
            try:
                os.unlink(dst)
            except OSError as e:
                raise CompileFileError(f"could not delete '{dst}': {e.strerror}")

        try:
            fdst = open(dst, 'wb')
        except OSError as e:
            raise CompileError(f"could not create '{dst}': {e.strerror}")

        while True:
            try:
                buf = fsrc.read(buffer_size)
            except OSError as e:
                raise CompileError(f"could not read from '{src}': {e.strerror}")

            if not buf:
                break

            try:
                fdst.write(buf)
            except OSError as e:
                raise CompileFileError(f"could not write to '{dst}': {e.strerror}")
    finally:
        if fdst:
            fdst.close()
        if fsrc:
            fsrc.close()


def copy_file(  # noqa: C901
    src,
    dst,
    preserve_mode=True,
    preserve_times=True,
    update=False,
    link=None,
    verbose=True,
    dry_run=False,
):
    """Copy a file 'src' to 'dst'.  If 'dst' is a directory, then 'src' is
    copied there with the same name; otherwise, it must be a filename.  (If
    the file exists, it will be ruthlessly clobbered.)  If 'preserve_mode'
    is true (the default), the file's mode (type and permission bits, or
    whatever is analogous on the current platform) is copied.  If
    'preserve_times' is true (the default), the last-modified and
    last-access times are copied as well.  If 'update' is true, 'src' will
    only be copied if 'dst' does not exist, or if 'dst' does exist but is
    older than 'src'.

    'link' allows you to make hard links (os.link) or symbolic links
    (os.symlink) instead of copying: set it to "hard" or "sym"; if it is
    None (the default), files are copied.  Don't set 'link' on systems that
    don't support it: 'copy_file()' doesn't check if hard or symbolic
    linking is available. If hardlink fails, falls back to
    _copy_file_contents().

    Under Mac OS, uses the native file copy function in macostools; on
    other systems, uses '_copy_file_contents()' to copy file contents.

    Return a tuple (dest_name, copied): 'dest_name' is the actual name of
    the output file, and 'copied' is true if the file was copied (or would
    have been copied, if 'dry_run' true).
    """
    # XXX if the destination file already exists, we clobber it if
    # copying, but blow up if linking.  Hmmm.  And I don't know what
    # macostools.copyfile() does.  Should definitely be consistent, and
    # should probably blow up if destination exists and we would be
    # changing it (ie. it's not already a hard/soft link to src OR
    # (not update) and (src newer than dst).

    from ._modified import newer
    from stat import S_IMODE, ST_ATIME, ST_MODE, ST_MTIME

    if not os.path.isfile(src):
        raise FileError(
            f"can't copy '{src}': doesn't exist or not a regular file"
        )

    if os.path.isdir(dst):
        dir = dst
        dst = os.path.join(dst, os.path.basename(src))
    else:
        dir = os.path.dirname(dst)

    if update and not newer(src, dst):
        if verbose >= 1:
            log.debug("not copying %s (output up-to-date)", src)
        return (dst, False)

    try:
        action = _copy_action[link]
    except KeyError:
        raise ValueError(f"invalid value '{link}' for 'link' argument")

    if verbose >= 1:
        if os.path.basename(dst) == os.path.basename(src):
            log.info("%s %s -> %s", action, src, dir)
        else:
            log.info("%s %s -> %s", action, src, dst)

    if dry_run:
        return (dst, True)

    # If linking (hard or symbolic), use the appropriate system call
    # (Unix only, of course, but that's the caller's responsibility)
    elif link == 'hard':
        if not (os.path.exists(dst) and os.path.samefile(src, dst)):
            try:
                os.link(src, dst)
            except OSError:
                # If hard linking fails, fall back on copying file
                # (some special filesystems don't support hard linking
                #  even under Unix, see issue #8876).
                pass
            else:
                return (dst, True)
    elif link == 'sym':
        if not (os.path.exists(dst) and os.path.samefile(src, dst)):
            os.symlink(src, dst)
            return (dst, True)

    # Otherwise (non-Mac, not linking), copy the file contents and
    # (optionally) copy the times and mode.
    _copy_file_contents(src, dst)
    if preserve_mode or preserve_times:
        st = os.stat(src)

        # According to David Ascher <da@ski.org>, utime() should be done
        # before chmod() (at least under NT).
        if preserve_times:
            os.utime(dst, (st[ST_ATIME], st[ST_MTIME]))
        if preserve_mode:
            os.chmod(dst, S_IMODE(st[ST_MODE]))

    return (dst, True)


# XXX I suspect this is Unix-specific -- need porting help!
def move_file(src, dst, verbose=True, dry_run=False):  # noqa: C901
    """Move a file 'src' to 'dst'.  If 'dst' is a directory, the file will
    be moved into it with the same name; otherwise, 'src' is just renamed
    to 'dst'.  Return the new full name of the file.

    Handles cross-device moves on Unix using 'copy_file()'.  What about
    other systems???
    """
    import errno
    from os.path import basename, dirname, exists, isdir, isfile

    if verbose >= 1:
        log.info("moving %s -> %s", src, dst)

    if dry_run:
        return dst

    if not isfile(src):
        raise FileError(f"can't move '{src}': not a regular file")

    if isdir(dst):
        dst = os.path.join(dst, basename(src))
    elif exists(dst):
        raise FileError(
            f"can't move '{src}': destination '{dst}' already exists"
        )

    if not isdir(dirname(dst)):
        raise FileError(
            f"can't move '{src}': destination '{dst}' not a valid path"
        )

    copy_it = False
    try:
        os.rename(src, dst)
    except OSError as e:
        (num, msg) = e.args
        if num == errno.EXDEV:
            copy_it = True
        else:
            raise FileError(f"couldn't move '{src}' to '{dst}': {msg}")

    if copy_it:
        copy_file(src, dst, verbose=verbose)
        try:
            os.unlink(src)
        except OSError as e:
            (num, msg) = e.args
            try:
                os.unlink(dst)
            except OSError:
                pass
            raise FileError(
                f"couldn't move '{src}' to '{dst}' by copy/delete: "
                f"delete '{src}' failed: {msg}"
            )
    return dst


def write_file(filename, contents):
    """Create a file with the specified name and write 'contents' (a
    sequence of strings without line terminators) to it.
    """
    with open(filename, 'w', encoding='utf-8') as f:
        f.writelines(line + '\n' for line in contents)

class SkipRepeatAbsolutePaths(set):
    """
    Cache for mkpath.

    In addition to cheapening redundant calls, eliminates redundant
    "creating /foo/bar/baz" messages in dry-run mode.
    """

    def __init__(self):
        SkipRepeatAbsolutePaths.instance = self

    @classmethod
    def clear(cls):
        super(cls, cls.instance).clear()

    def wrap(self, func):
        @functools.wraps(func)
        def wrapper(path, *args, **kwargs):
            if path.absolute() in self:
                return
            result = func(path, *args, **kwargs)
            self.add(path.absolute())
            return result

        return wrapper


# Python 3.8 compatibility
wrapper = SkipRepeatAbsolutePaths().wrap


@functools.singledispatch
@wrapper
def mkpath(name: Path, mode=0o777, verbose=True, dry_run=False) -> None:
    """Create a directory and any missing ancestor directories.

    If the directory already exists (or if 'name' is the empty string, which
    means the current directory, which of course exists), then do nothing.
    Raise FileError if unable to create some directory along the way
    (eg. some sub-path exists, but is a file rather than a directory).
    If 'verbose' is true, log the directory created.
    """
    if verbose and not name.is_dir():
        log.info("creating %s", name)

    try:
        dry_run or name.mkdir(mode=mode, parents=True, exist_ok=True)
    except OSError as exc:
        raise FileError(f"could not create '{name}': {exc.args[-1]}")


@mkpath.register
def _(name: str, *args, **kwargs):
    return mkpath(Path(name), *args, **kwargs)


@mkpath.register
def _(name: None, *args, **kwargs):
    """
    Detect a common bug -- name is None.
    """
    raise InternalError(f"mkpath: 'name' must be a string (got {name!r})")


def create_tree(base_dir, files, mode=0o777, verbose=True, dry_run=False):
    """Create all the empty directories under 'base_dir' needed to put 'files'
    there.

    'base_dir' is just the name of a directory which doesn't necessarily
    exist yet; 'files' is a list of filenames to be interpreted relative to
    'base_dir'.  'base_dir' + the directory portion of every file in 'files'
    will be created if it doesn't already exist.  'mode', 'verbose' and
    'dry_run' flags are as for 'mkpath()'.
    """
    # First get the list of directories to create
    need_dir = set(os.path.join(base_dir, os.path.dirname(file)) for file in files)

    # Now create them
    for dir in sorted(need_dir):
        mkpath(dir, mode, verbose=verbose, dry_run=dry_run)


def copy_tree(
    src,
    dst,
    preserve_mode=True,
    preserve_times=True,
    preserve_symlinks=False,
    update=False,
    verbose=True,
    dry_run=False,
):
    """Copy an entire directory tree 'src' to a new location 'dst'.

    Both 'src' and 'dst' must be directory names.  If 'src' is not a
    directory, raise FileError.  If 'dst' does not exist, it is
    created with 'mkpath()'.  The end result of the copy is that every
    file in 'src' is copied to 'dst', and directories under 'src' are
    recursively copied to 'dst'.  Return the list of files that were
    copied or might have been copied, using their output name.  The
    return value is unaffected by 'update' or 'dry_run': it is simply
    the list of all files under 'src', with the names changed to be
    under 'dst'.

    'preserve_mode' and 'preserve_times' are the same as for
    'copy_file'; note that they only apply to regular files, not to
    directories.  If 'preserve_symlinks' is true, symlinks will be
    copied as symlinks (on platforms that support them!); otherwise
    (the default), the destination of the symlink will be copied.
    'update' and 'verbose' are the same as for 'copy_file'.
    """
    if not dry_run and not os.path.isdir(src):
        raise FileError(f"cannot copy tree '{src}': not a directory")
    try:
        names = os.listdir(src)
    except OSError as e:
        if dry_run:
            names = []
        else:
            raise FileError(f"error listing files in '{src}': {e.strerror}")

    if not dry_run:
        mkpath(dst, verbose=verbose)

    copy_one = functools.partial(
        _copy_one,
        src=src,
        dst=dst,
        preserve_symlinks=preserve_symlinks,
        verbose=verbose,
        dry_run=dry_run,
        preserve_mode=preserve_mode,
        preserve_times=preserve_times,
        update=update,
    )
    return list(itertools.chain.from_iterable(map(copy_one, names)))


def _copy_one(
    name,
    *,
    src,
    dst,
    preserve_symlinks,
    verbose,
    dry_run,
    preserve_mode,
    preserve_times,
    update,
):
    src_name = os.path.join(src, name)
    dst_name = os.path.join(dst, name)

    if name.startswith('.nfs'):
        # skip NFS rename files
        return

    if preserve_symlinks and os.path.islink(src_name):
        link_dest = os.readlink(src_name)
        if verbose >= 1:
            log.info("linking %s -> %s", dst_name, link_dest)
        if not dry_run:
            os.symlink(link_dest, dst_name)
        yield dst_name

    elif os.path.isdir(src_name):
        yield from copy_tree(
            src_name,
            dst_name,
            preserve_mode,
            preserve_times,
            preserve_symlinks,
            update,
            verbose=verbose,
            dry_run=dry_run,
        )
    else:
        copy_file(
            src_name,
            dst_name,
            preserve_mode,
            preserve_times,
            update,
            verbose=verbose,
            dry_run=dry_run,
        )
        yield dst_name


def _build_cmdtuple(path, cmdtuples):
    """Helper for remove_tree()."""
    for f in os.listdir(path):
        real_f = os.path.join(path, f)
        if os.path.isdir(real_f) and not os.path.islink(real_f):
            _build_cmdtuple(real_f, cmdtuples)
        else:
            cmdtuples.append((os.remove, real_f))
    cmdtuples.append((os.rmdir, path))


def remove_tree(directory, verbose=True, dry_run=False):
    """Recursively remove an entire directory tree.

    Any errors are ignored (apart from being reported to stdout if 'verbose'
    is true).
    """
    if verbose >= 1:
        log.info("removing '%s' (and everything under it)", directory)
    if dry_run:
        return
    cmdtuples = []
    _build_cmdtuple(directory, cmdtuples)
    for cmd in cmdtuples:
        try:
            cmd[0](cmd[1])
            # Clear the cache
            SkipRepeatAbsolutePaths.clear()
        except OSError as exc:
            log.warning("error removing %s: %s", directory, exc)


def ensure_relative(path):
    """Take the full path 'path', and make it a relative path.

    This is useful to make 'path' the second argument to os.path.join().
    """
    drive, path = os.path.splitdrive(path)
    if path[0:1] == os.sep:
        path = drive + path[1:]
    return path


def _get_gid(name):
    """Returns a gid, given a group name."""
    if getgrnam is None or name is None:
        return None
    try:
        result = getgrnam(name)
    except KeyError:
        result = None
    if result is not None:
        return result[2]
    return None


def _get_uid(name):
    """Returns an uid, given a user name."""
    if getpwnam is None or name is None:
        return None
    try:
        result = getpwnam(name)
    except KeyError:
        result = None
    if result is not None:
        return result[2]
    return None


def make_tarball(
    base_name,
    base_dir,
    compress="gzip",
    verbose=False,
    dry_run=False,
    owner=None,
    group=None,
):
    """Create a (possibly compressed) tar file from all the files under
    'base_dir'.

    'compress' must be "gzip" (the default), "bzip2", "xz", or None.

    'owner' and 'group' can be used to define an owner and a group for the
    archive that is being built. If not provided, the current owner and group
    will be used.

    The output tar file will be named 'base_dir' +  ".tar", possibly plus
    the appropriate compression extension (".gz", ".bz2", ".xz" or ".Z").

    Returns the output filename.
    """
    tar_compression = {
        'gzip': 'gz',
        'bzip2': 'bz2',
        'xz': 'xz',
        None: '',
    }
    compress_ext = {'gzip': '.gz', 'bzip2': '.bz2', 'xz': '.xz'}

    # flags for compression program, each element of list will be an argument
    if compress is not None and compress not in compress_ext.keys():
        raise ValueError(
            "bad value for 'compress': must be None, 'gzip', 'bzip2', 'xz'"
        )

    archive_name = base_name + '.tar'
    archive_name += compress_ext.get(compress, '')

    mkpath(os.path.dirname(archive_name), dry_run=dry_run)

    # creating the tarball
    import tarfile  # late import so Python build itself doesn't break

    log.info('Creating tar archive')

    uid = _get_uid(owner)
    gid = _get_gid(group)

    def _set_uid_gid(tarinfo):
        if gid is not None:
            tarinfo.gid = gid
            tarinfo.gname = group
        if uid is not None:
            tarinfo.uid = uid
            tarinfo.uname = owner
        return tarinfo

    if not dry_run:
        tar = tarfile.open(archive_name, f'w|{tar_compression[compress]}')
        try:
            tar.add(base_dir, filter=_set_uid_gid)
        finally:
            tar.close()

    return archive_name


def make_zipfile(base_name, base_dir, verbose=False, dry_run=False):  # noqa: C901
    """Create a zip file from all the files under 'base_dir'.

    The output zip file will be named 'base_name' + ".zip".  Uses either the
    "zipfile" Python module (if available) or the InfoZIP "zip" utility
    (if installed and found on the default search path).  If neither tool is
    available, raises ExecError.  Returns the name of the output zip
    file.
    """
    zip_filename = base_name + ".zip"
    mkpath(os.path.dirname(zip_filename), dry_run=dry_run)

    # If zipfile module is not available, try spawning an external
    # 'zip' command.
    if zipfile is None:
        if verbose:
            zipoptions = "-r"
        else:
            zipoptions = "-rq"

        try:
            spawn(["zip", zipoptions, zip_filename, base_dir], dry_run=dry_run)
        except ExecError:
            # XXX really should distinguish between "couldn't find
            # external 'zip' command" and "zip failed".
            raise ExecError(
                f"unable to create zip file '{zip_filename}': "
                "could neither import the 'zipfile' module nor "
                "find a standalone zip utility"
            )

    else:
        log.info("creating '%s' and adding '%s' to it", zip_filename, base_dir)

        if not dry_run:
            try:
                zip = zipfile.ZipFile(
                    zip_filename, "w", compression=zipfile.ZIP_DEFLATED
                )
            except RuntimeError:
                zip = zipfile.ZipFile(zip_filename, "w", compression=zipfile.ZIP_STORED)

            with zip:
                if base_dir != os.curdir:
                    path = os.path.normpath(os.path.join(base_dir, ''))
                    zip.write(path, path)
                    log.info("adding '%s'", path)
                for dirpath, dirnames, filenames in os.walk(base_dir):
                    for name in dirnames:
                        path = os.path.normpath(os.path.join(dirpath, name, ''))
                        zip.write(path, path)
                        log.info("adding '%s'", path)
                    for name in filenames:
                        path = os.path.normpath(os.path.join(dirpath, name))
                        if os.path.isfile(path):
                            zip.write(path, path)
                            log.info("adding '%s'", path)

    return zip_filename


ARCHIVE_FORMATS = {
    'gztar': (make_tarball, [('compress', 'gzip')], "gzip'ed tar-file"),
    'bztar': (make_tarball, [('compress', 'bzip2')], "bzip2'ed tar-file"),
    'xztar': (make_tarball, [('compress', 'xz')], "xz'ed tar-file"),
    'ztar': (make_tarball, [('compress', 'compress')], "compressed tar file"),
    'tar': (make_tarball, [('compress', None)], "uncompressed tar file"),
    'zip': (make_zipfile, [], "ZIP file"),
}


def check_archive_formats(formats):
    """Returns the first format from the 'format' list that is unknown.

    If all formats are known, returns None
    """
    for format in formats:
        if format not in ARCHIVE_FORMATS:
            return format
    return None


def make_archive(
    base_name,
    format,
    root_dir=None,
    base_dir=None,
    verbose=False,
    dry_run=False,
    owner=None,
    group=None,
):
    """Create an archive file (eg. zip or tar).

    'base_name' is the name of the file to create, minus any format-specific
    extension; 'format' is the archive format: one of "zip", "tar", "gztar",
    "bztar", "xztar", or "ztar".

    'root_dir' is a directory that will be the root directory of the
    archive; ie. we typically chdir into 'root_dir' before creating the
    archive.  'base_dir' is the directory where we start archiving from;
    ie. 'base_dir' will be the common prefix of all files and
    directories in the archive.  'root_dir' and 'base_dir' both default
    to the current directory.  Returns the name of the archive file.

    'owner' and 'group' are used when creating a tar archive. By default,
    uses the current owner and group.
    """
    save_cwd = os.getcwd()
    if root_dir is not None:
        log.debug("changing into '%s'", root_dir)
        base_name = os.path.abspath(base_name)
        if not dry_run:
            os.chdir(root_dir)

    if base_dir is None:
        base_dir = os.curdir

    kwargs = {'dry_run': dry_run}

    try:
        format_info = ARCHIVE_FORMATS[format]
    except KeyError:
        raise ValueError(f"unknown archive format '{format}'")

    func = format_info[0]
    kwargs.update(format_info[1])

    if format != 'zip':
        kwargs['owner'] = owner
        kwargs['group'] = group

    try:
        filename = func(base_name, base_dir, **kwargs)
    finally:
        if root_dir is not None:
            log.debug("changing back to '%s'", save_cwd)
            os.chdir(save_cwd)

    return filename


class Command:
    """Abstract base class for defining command classes, the "worker bees"
    of the .  A useful analogy for command classes is to think of
    them as subroutines with local variables called "options".  The options
    are "declared" in 'initialize_options()' and "defined" (given their
    final values, aka "finalized") in 'finalize_options()', both of which
    must be defined by every command class.  The distinction between the
    two is necessary because option values might come from the outside
    world (command line, config file, ...), and any options dependent on
    other options must be computed *after* these outside influences have
    been processed -- hence 'finalize_options()'.  The "body" of the
    subroutine, where it does all its work based on the values of its
    options, is the 'run()' method, which must also be implemented by every
    command class.
    """

    # 'sub_commands' formalizes the notion of a "family" of commands,
    # eg. "install" as the parent with sub-commands "install_lib",
    # "install_headers", etc.  The parent of a family of commands
    # defines 'sub_commands' as a class attribute; it's a list of
    #    (command_name : string, predicate : unbound_method | string | None)
    # tuples, where 'predicate' is a method of the parent command that
    # determines whether the corresponding command is applicable in the
    # current situation.  (Eg. we "install_headers" is only applicable if
    # we have any C header files to install.)  If 'predicate' is None,
    # that command is always applicable.
    #
    # 'sub_commands' is usually defined at the *end* of a class, because
    # predicates can be unbound methods, so they must already have been
    # defined.  The canonical example is the "install" command.
    sub_commands: ClassVar[  # Any to work around variance issues
        list[tuple[str, Callable[[Any], bool] | None]]
    ] = []

    user_options: ClassVar[
        # Specifying both because list is invariant. Avoids mypy override assignment issues
        list[tuple[str, str, str]] | list[tuple[str, str | None, str]]
    ] = []

    # -- Creation/initialization methods -------------------------------

    def __init__(self, dist):
        """Create and initialize a new Command object.  Most importantly,
        invokes the 'initialize_options()' method, which is the real
        initializer and depends on the actual command being
        instantiated.
        """
        # late import because of mutual dependence between these classes
        from setuptools.dist import Distribution

        if not isinstance(dist, Distribution):
            raise TypeError("dist must be a Distribution instance")
        if self.__class__ is Command:
            raise RuntimeError("Command is an abstract class")

        self.distribution = dist
        self.initialize_options()

        # Per-command versions of the global flags, so that the user can
        # customize ' behaviour command-by-command and let some
        # commands fall back on the Distribution's behaviour.  None means
        # "not defined, check self.distribution's copy", while 0 or 1 mean
        # false and true (duh).  Note that this means figuring out the real
        # value of each flag is a touch complicated -- hence "self._dry_run"
        # will be handled by __getattr__, below.
        # XXX This needs to be fixed.
        self._dry_run = None

        # verbose is largely ignored, but needs to be set for
        # backwards compatibility (I think)?
        self.verbose = dist.verbose

        # Some commands define a 'self.force' option to ignore file
        # timestamps, but methods defined *here* assume that
        # 'self.force' exists for all commands.  So define it here
        # just to be safe.
        self.force = None

        # The 'help' flag is just used for command-line parsing, so
        # none of that complicated bureaucracy is needed.
        self.help = False

        # 'finalized' records whether or not 'finalize_options()' has been
        # called.  'finalize_options()' itself should not pay attention to
        # this flag: it is the business of 'ensure_finalized()', which
        # always calls 'finalize_options()', to respect/update it.
        self.finalized = False

    # XXX A more explicit way to customize dry_run would be better.
    def __getattr__(self, attr):
        if attr == 'dry_run':
            myval = getattr(self, "_" + attr)
            if myval is None:
                return getattr(self.distribution, attr)
            else:
                return myval
        else:
            raise AttributeError(attr)

    def ensure_finalized(self):
        if not self.finalized:
            self.finalize_options()
        self.finalized = True

    # Subclasses must define:
    #   initialize_options()
    #     provide default values for all options; may be customized by
    #     setup script, by options from config file(s), or by command-line
    #     options
    #   finalize_options()
    #     decide on the final values for all options; this is called
    #     after all possible intervention from the outside world
    #     (command-line, option file, etc.) has been processed
    #   run()
    #     run the command: do whatever it is we're here to do,
    #     controlled by the command's various option values

    def initialize_options(self):
        """Set default values for all the options that this command
        supports.  Note that these defaults may be overridden by other
        commands, by the setup script, by config files, or by the
        command-line.  Thus, this is not the place to code dependencies
        between options; generally, 'initialize_options()' implementations
        are just a bunch of "self.foo = None" assignments.

        This method must be implemented by all command classes.
        """
        raise RuntimeError(
            f"abstract method -- subclass {self.__class__} must override"
        )

    def finalize_options(self):
        """Set final values for all the options that this command supports.
        This is always called as late as possible, ie.  after any option
        assignments from the command-line or from other commands have been
        done.  Thus, this is the place to code option dependencies: if
        'foo' depends on 'bar', then it is safe to set 'foo' from 'bar' as
        long as 'foo' still has the same value it was assigned in
        'initialize_options()'.

        This method must be implemented by all command classes.
        """
        raise RuntimeError(
            f"abstract method -- subclass {self.__class__} must override"
        )

    def dump_options(self, header=None, indent=""):
        from setuptools._distutils.fancy_getopt import longopt_xlate

        if header is None:
            header = f"command options for '{self.get_command_name()}':"
        self.announce(indent + header, level=logging.INFO)
        indent = indent + "  "
        for option, _, _ in self.user_options:
            option = option.translate(longopt_xlate)
            if option[-1] == "=":
                option = option[:-1]
            value = getattr(self, option)
            self.announce(indent + f"{option} = {value}", level=logging.INFO)

    def run(self):
        """A command's raison d'etre: carry out the action it exists to
        perform, controlled by the options initialized in
        'initialize_options()', customized by other commands, the setup
        script, the command-line, and config files, and finalized in
        'finalize_options()'.  All terminal output and filesystem
        interaction should be done by 'run()'.

        This method must be implemented by all command classes.
        """
        raise RuntimeError(
            f"abstract method -- subclass {self.__class__} must override"
        )

    def announce(self, msg, level=logging.DEBUG):
        log.log(level, msg)

    def debug_print(self, msg):
        """Print 'msg' to stdout if the global DEBUG (taken from the
        DISTUTILS_DEBUG environment variable) flag is true.
        """
        from setuptools._distutils.debug import DEBUG

        if DEBUG:
            print(msg)
            sys.stdout.flush()

    # -- Option validation methods -------------------------------------
    # (these are very handy in writing the 'finalize_options()' method)
    #
    # NB. the general philosophy here is to ensure that a particular option
    # value meets certain type and value constraints.  If not, we try to
    # force it into conformance (eg. if we expect a list but have a string,
    # split the string on comma and/or whitespace).  If we can't force the
    # option into conformance, raise OptionError.  Thus, command
    # classes need do nothing more than (eg.)
    #   self.ensure_string_list('foo')
    # and they can be guaranteed that thereafter, self.foo will be
    # a list of strings.

    def _ensure_stringlike(self, option, what, default=None):
        val = getattr(self, option)
        if val is None:
            setattr(self, option, default)
            return default
        elif not isinstance(val, str):
            raise OptionError(f"'{option}' must be a {what} (got `{val}`)")
        return val

    def ensure_string(self, option, default=None):
        """Ensure that 'option' is a string; if not defined, set it to
        'default'.
        """
        self._ensure_stringlike(option, "string", default)

    def ensure_string_list(self, option):
        r"""Ensure that 'option' is a list of strings.  If 'option' is
        currently a string, we split it either on /,\s*/ or /\s+/, so
        "foo bar baz", "foo,bar,baz", and "foo,   bar baz" all become
        ["foo", "bar", "baz"].
        """
        val = getattr(self, option)
        if val is None:
            return
        elif isinstance(val, str):
            setattr(self, option, re.split(r',\s*|\s+', val))
        else:
            if isinstance(val, list):
                ok = all(isinstance(v, str) for v in val)
            else:
                ok = False
            if not ok:
                raise OptionError(
                    f"'{option}' must be a list of strings (got {val!r})"
                )

    def _ensure_tested_string(self, option, tester, what, error_fmt, default=None):
        val = self._ensure_stringlike(option, what, default)
        if val is not None and not tester(val):
            raise OptionError(
                ("error in '%s' option: " + error_fmt) % (option, val)
            )

    def ensure_filename(self, option):
        """Ensure that 'option' is the name of an existing file."""
        self._ensure_tested_string(
            option, os.path.isfile, "filename", "'%s' does not exist or is not a file"
        )

    def ensure_dirname(self, option):
        self._ensure_tested_string(
            option,
            os.path.isdir,
            "directory name",
            "'%s' does not exist or is not a directory",
        )

    # -- Convenience methods for commands ------------------------------

    def get_command_name(self):
        if hasattr(self, 'command_name'):
            return self.command_name
        else:
            return self.__class__.__name__

    def set_undefined_options(self, src_cmd, *option_pairs):
        """Set the values of any "undefined" options from corresponding
        option values in some other command object.  "Undefined" here means
        "is None", which is the convention used to indicate that an option
        has not been changed between 'initialize_options()' and
        'finalize_options()'.  Usually called from 'finalize_options()' for
        options that depend on some other command rather than another
        option of the same command.  'src_cmd' is the other command from
        which option values will be taken (a command object will be created
        for it if necessary); the remaining arguments are
        '(src_option,dst_option)' tuples which mean "take the value of
        'src_option' in the 'src_cmd' command object, and copy it to
        'dst_option' in the current command object".
        """
        # Option_pairs: list of (src_option, dst_option) tuples
        src_cmd_obj = self.distribution.get_command_obj(src_cmd)
        src_cmd_obj.ensure_finalized()
        for src_option, dst_option in option_pairs:
            if getattr(self, dst_option) is None:
                setattr(self, dst_option, getattr(src_cmd_obj, src_option))

    def get_finalized_command(self, command, create=True):
        """Wrapper around Distribution's 'get_command_obj()' method: find
        (create if necessary and 'create' is true) the command object for
        'command', call its 'ensure_finalized()' method, and return the
        finalized command object.
        """
        cmd_obj = self.distribution.get_command_obj(command, create)
        cmd_obj.ensure_finalized()
        return cmd_obj

    # XXX rename to 'get_reinitialized_command()'? (should do the
    # same in dist.py, if so)
    @overload
    def reinitialize_command(
        self, command: str, reinit_subcommands: bool = False
    ) -> Command: ...
    @overload
    def reinitialize_command(
        self, command: _CommandT, reinit_subcommands: bool = False
    ) -> _CommandT: ...
    def reinitialize_command(
        self, command: str | Command, reinit_subcommands=False
    ) -> Command:
        return self.distribution.reinitialize_command(command, reinit_subcommands)

    def run_command(self, command):
        """Run some other command: uses the 'run_command()' method of
        Distribution, which creates and finalizes the command object if
        necessary and then invokes its 'run()' method.
        """
        self.distribution.run_command(command)

    def get_sub_commands(self):
        """Determine the sub-commands that are relevant in the current
        distribution (ie., that need to be run).  This is based on the
        'sub_commands' class attribute: each tuple in that list may include
        a method that we call to determine if the subcommand needs to be
        run for the current distribution.  Return a list of command names.
        """
        commands = []
        for cmd_name, method in self.sub_commands:
            if method is None or method(self):
                commands.append(cmd_name)
        return commands

    # -- External world manipulation -----------------------------------

    def warn(self, msg):
        log.warning("warning: %s: %s\n", self.get_command_name(), msg)

    def execute(self, func, args, msg=None, level=1):
        execute(func, args, msg, dry_run=self.dry_run)

    def mkpath(self, name, mode=0o777):
        mkpath(name, mode, dry_run=self.dry_run)

    def copy_file(
        self,
        infile,
        outfile,
        preserve_mode=True,
        preserve_times=True,
        link=None,
        level=1,
    ):
        """Copy a file respecting verbose, dry-run and force flags.  (The
        former two default to whatever is in the Distribution object, and
        the latter defaults to false for commands that don't define it.)"""
        return copy_file(
            infile,
            outfile,
            preserve_mode,
            preserve_times,
            not self.force,
            link,
            dry_run=self.dry_run,
        )

    def copy_tree(
        self,
        infile,
        outfile,
        preserve_mode=True,
        preserve_times=True,
        preserve_symlinks=False,
        level=1,
    ):
        """Copy an entire directory tree respecting verbose, dry-run,
        and force flags.
        """
        return copy_tree(
            infile,
            outfile,
            preserve_mode,
            preserve_times,
            preserve_symlinks,
            not self.force,
            dry_run=self.dry_run,
        )

    def move_file(self, src, dst, level=1):
        """Move a file respecting dry-run flag."""
        return move_file(src, dst, dry_run=self.dry_run)

    def spawn(self, cmd, search_path=True, level=1):
        """Spawn an external command respecting dry-run flag."""

        spawn(cmd, search_path, dry_run=self.dry_run)

    def make_archive(
        self, base_name, format, root_dir=None, base_dir=None, owner=None, group=None
    ):
        return make_archive(
            base_name,
            format,
            root_dir,
            base_dir,
            dry_run=self.dry_run,
            owner=owner,
            group=group,
        )

    def make_file(
        self, infiles, outfile, func, args, exec_msg=None, skip_msg=None, level=1
    ):
        """Special case of 'execute()' for operations that process one or
        more input files and generate one output file.  Works just like
        'execute()', except the operation is skipped and a different
        message printed if 'outfile' already exists and is newer than all
        files listed in 'infiles'.  If the command defined 'self.force',
        and it is true, then the command is unconditionally run -- does no
        timestamp checks.
        """
        if skip_msg is None:
            skip_msg = f"skipping {outfile} (inputs unchanged)"

        # Allow 'infiles' to be a single string
        if isinstance(infiles, str):
            infiles = (infiles,)
        elif not isinstance(infiles, (list, tuple)):
            raise TypeError("'infiles' must be a string, or a list or tuple of strings")

        if exec_msg is None:
            exec_msg = "generating {} from {}".format(outfile, ', '.join(infiles))

        # If 'outfile' must be regenerated (either because it doesn't
        # exist, is out-of-date, or the 'force' flag is true) then
        # perform the action that presumably regenerates it
        if self.force or _modified.newer_group(infiles, outfile):
            self.execute(func, args, exec_msg, level)
        # Otherwise, print the "skip" message
        else:
            log.debug(skip_msg)
