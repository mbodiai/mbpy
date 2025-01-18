"""distutils.command.config

Implements the Distutils 'config' command, a (mostly) empty command class
that exists mainly to be sub-classed by specific module distributions and
applications.  The idea is that while every "config" command is different,
at least they're all named the same, and users always see "config" in the
list of standard commands.  Also, this is a good place to put common
configure-like tasks: "try to compile this C code", or "figure out where
this header file lives".
"""

import os, re


from mbpy import log

import os
import pathlib
import re
import sys
import types
import warnings
import functools
import os
import pathlib
import re
import sys
import sysconfig



from more_itertools import always_iterable
from mbpy.helpers._dist import Command,is_mingw, PlatformError, split_quoted, passnone, get_config_var, get_config_vars, get_python_version, get_python_inc, get_python_lib, customize_compiler, get_config_h_filename, get_makefile_filename, parse_config_h, parse_makefile, expand_makefile_vars, CCompiler


LANG_EXT = {"c": ".c", "c++": ".cxx"}
"""Provide access to Python's configuration information.  The specific
configuration variables available depend heavily on the platform and
configuration.  The values may be retrieved using
get_config_var(name), and the list of variables is available via
get_config_vars().keys().  Additional convenience functions are also
available.

Written by:   Fred L. Drake, Jr.
Email:        <fdrake@acm.org>
"""



IS_PYPY = '__pypy__' in sys.builtin_module_names

# These are needed in a couple of spots, so just compute them once.
PREFIX = os.path.normpath(sys.prefix)
EXEC_PREFIX = os.path.normpath(sys.exec_prefix)
BASE_PREFIX = os.path.normpath(sys.base_prefix)
BASE_EXEC_PREFIX = os.path.normpath(sys.base_exec_prefix)

# Path to the base directory of the project. On Windows the binary may
# live in project/PCbuild/win32 or project/PCbuild/amd64.
# set for cross builds
if "_PYTHON_PROJECT_BASE" in os.environ:
    project_base = os.path.abspath(os.environ["_PYTHON_PROJECT_BASE"])
else:
    if sys.executable:
        project_base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        # sys.executable can be empty if argv[0] has been changed and Python is
        # unable to retrieve the real program name
        project_base = os.getcwd()


def _is_python_source_dir(d):
    """
    Return True if the target directory appears to point to an
    un-installed Python.
    """
    modules = pathlib.Path(d).joinpath('Modules')
    return any(modules.joinpath(fn).is_file() for fn in ('Setup', 'Setup.local'))


_sys_home = getattr(sys, '_home', None)


def _is_parent(dir_a, dir_b):
    """
    Return True if a is a parent of b.
    """
    return os.path.normcase(dir_a).startswith(os.path.normcase(dir_b))


if os.name == 'nt':

    @pass_none
    def _fix_pcbuild(d):
        # In a venv, sys._home will be inside BASE_PREFIX rather than PREFIX.
        prefixes = PREFIX, BASE_PREFIX
        matched = (
            prefix
            for prefix in prefixes
            if _is_parent(d, os.path.join(prefix, "PCbuild"))
        )
        return next(matched, d)

    project_base = _fix_pcbuild(project_base)
    _sys_home = _fix_pcbuild(_sys_home)


def _python_build():
    if _sys_home:
        return _is_python_source_dir(_sys_home)
    return _is_python_source_dir(project_base)


python_build = _python_build()


# Calculate the build qualifier flags if they are defined.  Adding the flags
# to the include and lib directories only makes sense for an installation, not
# an in-source build.
build_flags = ''
try:
    if not python_build:
        build_flags = sys.abiflags
except AttributeError:
    # It's not a configure-based build, so the sys module doesn't have
    # this attribute, which is fine.
    pass


def get_python_version():
    """Return a string containing the major and minor Python version,
    leaving off the patchlevel.  Sample return values could be '1.5'
    or '2.2'.
    """
    return f'{sys.version_info.major}.{sys.version_info.minor}'


def get_python_inc(plat_specific=False, prefix=None):
    """Return the directory containing installed Python header files.

    If 'plat_specific' is false (the default), this is the path to the
    non-platform-specific header files, i.e. Python.h and so on;
    otherwise, this is the path to platform-specific header files
    (namely pyconfig.h).

    If 'prefix' is supplied, use it instead of sys.base_prefix or
    sys.base_exec_prefix -- i.e., ignore 'plat_specific'.
    """
    default_prefix = BASE_EXEC_PREFIX if plat_specific else BASE_PREFIX
    resolved_prefix = prefix if prefix is not None else default_prefix
    # MinGW imitates posix like layout, but os.name != posix
    os_name = "posix" if is_mingw() else os.name
    try:
        getter = globals()[f'_get_python_inc_{os_name}']
    except KeyError:
        raise PlatformError(
            "I don't know where Python installs its C header files "
            f"on platform '{os.name}'"
        )
    return getter(resolved_prefix, prefix, plat_specific)


@pass_none
def _extant(path):
    """
    Replace path with None if it doesn't exist.
    """
    return path if os.path.exists(path) else None


def _get_python_inc_posix(prefix, spec_prefix, plat_specific):
    if IS_PYPY and sys.version_info < (3, 8):
        return os.path.join(prefix, 'include')
    return (
        _get_python_inc_posix_python(plat_specific)
        or _extant(_get_python_inc_from_config(plat_specific, spec_prefix))
        or _get_python_inc_posix_prefix(prefix)
    )


def _get_python_inc_posix_python(plat_specific):
    """
    Assume the executable is in the build directory. The
    pyconfig.h file should be in the same directory. Since
    the build directory may not be the source directory,
    use "srcdir" from the makefile to find the "Include"
    directory.
    """
    if not python_build:
        return
    if plat_specific:
        return _sys_home or project_base
    incdir = os.path.join(get_config_var('srcdir'), 'Include')
    return os.path.normpath(incdir)


def _get_python_inc_from_config(plat_specific, spec_prefix):
    """
    If no prefix was explicitly specified, provide the include
    directory from the config vars. Useful when
    cross-compiling, since the config vars may come from
    the host
    platform Python installation, while the current Python
    executable is from the build platform installation.

    >>> monkeypatch = getfixture('monkeypatch')
    >>> gpifc = _get_python_inc_from_config
    >>> monkeypatch.setitem(gpifc.__globals__, 'get_config_var', str.lower)
    >>> gpifc(False, '/usr/bin/')
    >>> gpifc(False, '')
    >>> gpifc(False, None)
    'includepy'
    >>> gpifc(True, None)
    'confincludepy'
    """
    if spec_prefix is None:
        return get_config_var('CONF' * plat_specific + 'INCLUDEPY')


def _get_python_inc_posix_prefix(prefix):
    implementation = 'pypy' if IS_PYPY else 'python'
    python_dir = implementation + get_python_version() + build_flags
    return os.path.join(prefix, "include", python_dir)


def _get_python_inc_nt(prefix, spec_prefix, plat_specific):
    if python_build:
        # Include both include dirs to ensure we can find pyconfig.h
        return (
            os.path.join(prefix, "include")
            + os.path.pathsep
            + os.path.dirname(sysconfig.get_config_h_filename())
        )
    return os.path.join(prefix, "include")


# allow this behavior to be monkey-patched. Ref pypa/distutils#2.
def _posix_lib(standard_lib, libpython, early_prefix, prefix):
    if standard_lib:
        return libpython
    else:
        return os.path.join(libpython, "site-packages")


def get_python_lib(plat_specific=False, standard_lib=False, prefix=None):
    """Return the directory containing the Python library (standard or
    site additions).

    If 'plat_specific' is true, return the directory containing
    platform-specific modules, i.e. any module from a non-pure-Python
    module distribution; otherwise, return the platform-shared library
    directory.  If 'standard_lib' is true, return the directory
    containing standard Python library modules; otherwise, return the
    directory for site-specific modules.

    If 'prefix' is supplied, use it instead of sys.base_prefix or
    sys.base_exec_prefix -- i.e., ignore 'plat_specific'.
    """

    if IS_PYPY and sys.version_info < (3, 8):
        # PyPy-specific schema
        if prefix is None:
            prefix = PREFIX
        if standard_lib:
            return os.path.join(prefix, "lib-python", sys.version_info.major)
        return os.path.join(prefix, 'site-packages')

    early_prefix = prefix

    if prefix is None:
        if standard_lib:
            prefix = plat_specific and BASE_EXEC_PREFIX or BASE_PREFIX
        else:
            prefix = plat_specific and EXEC_PREFIX or PREFIX

    if os.name == "posix" or is_mingw():
        if plat_specific or standard_lib:
            # Platform-specific modules (any module from a non-pure-Python
            # module distribution) or standard Python library modules.
            libdir = getattr(sys, "platlibdir", "lib")
        else:
            # Pure Python
            libdir = "lib"
        implementation = 'pypy' if IS_PYPY else 'python'
        libpython = os.path.join(prefix, libdir, implementation + get_python_version())
        return _posix_lib(standard_lib, libpython, early_prefix, prefix)
    elif os.name == "nt":
        if standard_lib:
            return os.path.join(prefix, "Lib")
        else:
            return os.path.join(prefix, "Lib", "site-packages")
    else:
        raise PlatformError(
            f"I don't know where Python installs its library on platform '{os.name}'"
        )


@functools.lru_cache
def _customize_macos():
    """
    Perform first-time customization of compiler-related
    config vars on macOS. Use after a compiler is known
    to be needed. This customization exists primarily to support Pythons
    from binary installers. The kind and paths to build tools on
    the user system may vary significantly from the system
    that Python itself was built on.  Also the user OS
    version and build tools may not support the same set
    of CPU architectures for universal builds.
    """

    sys.platform == "darwin" and __import__('_osx_support').customize_compiler(
        get_config_vars()
    )


def customize_compiler(compiler):
    """Do any platform-specific customization of a CCompiler instance.

    Mainly needed on Unix, so we can plug in the information that
    varies across Unices and is stored in Python's Makefile.
    """
    if compiler.compiler_type in ["unix", "cygwin"] or (
        compiler.compiler_type == "mingw32" and is_mingw()
    ):
        _customize_macos()

        (
            cc,
            cxx,
            cflags,
            ccshared,
            ldshared,
            ldcxxshared,
            shlib_suffix,
            ar,
            ar_flags,
        ) = get_config_vars(
            'CC',
            'CXX',
            'CFLAGS',
            'CCSHARED',
            'LDSHARED',
            'LDCXXSHARED',
            'SHLIB_SUFFIX',
            'AR',
            'ARFLAGS',
        )

        cxxflags = cflags

        if 'CC' in os.environ:
            newcc = os.environ['CC']
            if 'LDSHARED' not in os.environ and ldshared.startswith(cc):
                # If CC is overridden, use that as the default
                #       command for LDSHARED as well
                ldshared = newcc + ldshared[len(cc) :]
            cc = newcc
        cxx = os.environ.get('CXX', cxx)
        ldshared = os.environ.get('LDSHARED', ldshared)
        ldcxxshared = os.environ.get('LDCXXSHARED', ldcxxshared)
        cpp = os.environ.get(
            'CPP',
            cc + " -E",  # not always
        )

        ldshared = _add_flags(ldshared, 'LD')
        ldcxxshared = _add_flags(ldcxxshared, 'LD')
        cflags = os.environ.get('CFLAGS', cflags)
        ldshared = _add_flags(ldshared, 'C')
        cxxflags = os.environ.get('CXXFLAGS', cxxflags)
        ldcxxshared = _add_flags(ldcxxshared, 'CXX')
        cpp = _add_flags(cpp, 'CPP')
        cflags = _add_flags(cflags, 'CPP')
        cxxflags = _add_flags(cxxflags, 'CPP')
        ldshared = _add_flags(ldshared, 'CPP')
        ldcxxshared = _add_flags(ldcxxshared, 'CPP')

        ar = os.environ.get('AR', ar)

        archiver = ar + ' ' + os.environ.get('ARFLAGS', ar_flags)
        cc_cmd = cc + ' ' + cflags
        cxx_cmd = cxx + ' ' + cxxflags

        compiler.set_executables(
            preprocessor=cpp,
            compiler=cc_cmd,
            compiler_so=cc_cmd + ' ' + ccshared,
            compiler_cxx=cxx_cmd,
            compiler_so_cxx=cxx_cmd + ' ' + ccshared,
            linker_so=ldshared,
            linker_so_cxx=ldcxxshared,
            linker_exe=cc,
            linker_exe_cxx=cxx,
            archiver=archiver,
        )

        if 'RANLIB' in os.environ and compiler.executables.get('ranlib', None):
            compiler.set_executables(ranlib=os.environ['RANLIB'])

        compiler.shared_lib_extension = shlib_suffix


def get_config_h_filename():
    """Return full pathname of installed pyconfig.h file."""
    return sysconfig.get_config_h_filename()


def get_makefile_filename():
    """Return full pathname of installed Makefile from the Python build."""
    return sysconfig.get_makefile_filename()


def parse_config_h(fp, g=None):
    """Parse a config.h-style file.

    A dictionary containing name/value pairs is returned.  If an
    optional dictionary is passed in as the second argument, it is
    used instead of a new dictionary.
    """
    return sysconfig.parse_config_h(fp, vars=g)


# Regexes needed for parsing Makefile (and similar syntaxes,
# like old-style Setup files).
_variable_rx = re.compile(r"([a-zA-Z][a-zA-Z0-9_]+)\s*=\s*(.*)")
_findvar1_rx = re.compile(r"\$\(([A-Za-z][A-Za-z0-9_]*)\)")
_findvar2_rx = re.compile(r"\${([A-Za-z][A-Za-z0-9_]*)}")


def parse_makefile(fn, g=None):  # noqa: C901
    """Parse a Makefile-style file.

    A dictionary containing name/value pairs is returned.  If an
    optional dictionary is passed in as the second argument, it is
    used instead of a new dictionary.
    """
    from setuptools._distutils.text_file import TextFile

    fp = TextFile(
        fn,
        strip_comments=True,
        skip_blanks=True,
        join_lines=True,
        errors="surrogateescape",
    )

    if g is None:
        g = {}
    done = {}
    notdone = {}

    while True:
        line = fp.readline()
        if line is None:  # eof
            break
        m = _variable_rx.match(line)
        if m:
            n, v = m.group(1, 2)
            v = v.strip()
            # `$$' is a literal `$' in make
            tmpv = v.replace('$$', '')

            if "$" in tmpv:
                notdone[n] = v
            else:
                try:
                    v = int(v)
                except ValueError:
                    # insert literal `$'
                    done[n] = v.replace('$$', '$')
                else:
                    done[n] = v

    # Variables with a 'PY_' prefix in the makefile. These need to
    # be made available without that prefix through sysconfig.
    # Special care is needed to ensure that variable expansion works, even
    # if the expansion uses the name without a prefix.
    renamed_variables = ('CFLAGS', 'LDFLAGS', 'CPPFLAGS')

    # do variable interpolation here
    while notdone:
        for name in list(notdone):
            value = notdone[name]
            m = _findvar1_rx.search(value) or _findvar2_rx.search(value)
            if m:
                n = m.group(1)
                found = True
                if n in done:
                    item = str(done[n])
                elif n in notdone:
                    # get it on a subsequent round
                    found = False
                elif n in os.environ:
                    # do it like make: fall back to environment
                    item = os.environ[n]

                elif n in renamed_variables:
                    if name.startswith('PY_') and name[3:] in renamed_variables:
                        item = ""

                    elif 'PY_' + n in notdone:
                        found = False

                    else:
                        item = str(done['PY_' + n])
                else:
                    done[n] = item = ""
                if found:
                    after = value[m.end() :]
                    value = value[: m.start()] + item + after
                    if "$" in after:
                        notdone[name] = value
                    else:
                        try:
                            value = int(value)
                        except ValueError:
                            done[name] = value.strip()
                        else:
                            done[name] = value
                        del notdone[name]

                        if name.startswith('PY_') and name[3:] in renamed_variables:
                            name = name[3:]
                            if name not in done:
                                done[name] = value
            else:
                # bogus variable reference; just drop it since we can't deal
                del notdone[name]

    fp.close()

    # strip spurious spaces
    for k, v in done.items():
        if isinstance(v, str):
            done[k] = v.strip()

    # save the results in the global dictionary
    g.update(done)
    return g


def expand_makefile_vars(s, vars):
    """Expand Makefile-style variables -- "${foo}" or "$(foo)" -- in
    'string' according to 'vars' (a dictionary mapping variable names to
    values).  Variables not present in 'vars' are silently expanded to the
    empty string.  The variable values in 'vars' should not contain further
    variable expansions; if 'vars' is the output of 'parse_makefile()',
    you're fine.  Returns a variable-expanded version of 's'.
    """

    # This algorithm does multiple expansion, so if vars['foo'] contains
    # "${bar}", it will expand ${foo} to ${bar}, and then expand
    # ${bar}... and so forth.  This is fine as long as 'vars' comes from
    # 'parse_makefile()', which takes care of such expansions eagerly,
    # according to make's variable expansion semantics.

    while True:
        m = _findvar1_rx.search(s) or _findvar2_rx.search(s)
        if m:
            (beg, end) = m.span()
            s = s[0:beg] + vars.get(m.group(1)) + s[end:]
        else:
            break
    return s


_config_vars = None


def py39_add_ext_suffix(vars):
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


def get_config_vars(*args):
    """With no arguments, return a dictionary of all configuration
    variables relevant for the current platform.  Generally this includes
    everything needed to build extensions and install both pure modules and
    extensions.  On Unix, this means every variable defined in Python's
    installed Makefile; on Windows it's a much smaller set.

    With arguments, return a list of values that result from looking up
    each argument in the configuration variable dictionary.
    """
    global _config_vars
    if _config_vars is None:
        _config_vars = sysconfig.get_config_vars().copy()
        py39_add_ext_suffix(_config_vars)

    return [_config_vars.get(name) for name in args] if args else _config_vars


def get_config_var(name):
    """Return the value of a single variable using the dictionary
    returned by 'get_config_vars()'.  Equivalent to
    get_config_vars().get(name)
    """
    if name == 'SO':
        import warnings

        warnings.warn('SO is deprecated, use EXT_SUFFIX', DeprecationWarning, 2)
    return get_config_vars().get(name)


@pass_none
def _add_flags(value: str, type: str) -> str:
    """
    Add any flags from the environment for the given type.

    type is the prefix to FLAGS in the environment key (e.g. "C" for "CFLAGS").
    """
    flags = os.environ.get(f'{type}FLAGS')
    return f'{value} {flags}' if flags else value


"""distutils.ccompiler

Contains CCompiler, an abstract base class that defines the interface
for the Distutils compiler abstraction model."""





class CCompiler:
    """Abstract base class to define the interface that must be implemented
    by real compiler classes.  Also has some utility methods used by
    several compiler classes.

    The basic idea behind a compiler abstraction class is that each
    instance can be used for all the compile/link steps in building a
    single project.  Thus, attributes common to all of those compile and
    link steps -- include directories, macros to define, libraries to link
    against, etc. -- are attributes of the compiler instance.  To allow for
    variability in how individual files are treated, most of those
    attributes may be varied on a per-compilation or per-link basis.
    """

    # 'compiler_type' is a class attribute that identifies this class.  It
    # keeps code that wants to know what kind of compiler it's dealing with
    # from having to import all possible compiler classes just to do an
    # 'isinstance'.  In concrete CCompiler subclasses, 'compiler_type'
    # should really, really be one of the keys of the 'compiler_class'
    # dictionary (see below -- used by the 'new_compiler()' factory
    # function) -- authors of new compiler interface classes are
    # responsible for updating 'compiler_class'!
    compiler_type = None

    # XXX things not handled by this compiler abstraction model:
    #   * client can't provide additional options for a compiler,
    #     e.g. warning, optimization, debugging flags.  Perhaps this
    #     should be the domain of concrete compiler abstraction classes
    #     (UnixCCompiler, MSVCCompiler, etc.) -- or perhaps the base
    #     class should have methods for the common ones.
    #   * can't completely override the include or library searchg
    #     path, ie. no "cc -I -Idir1 -Idir2" or "cc -L -Ldir1 -Ldir2".
    #     I'm not sure how widely supported this is even by Unix
    #     compilers, much less on other platforms.  And I'm even less
    #     sure how useful it is; maybe for cross-compiling, but
    #     support for that is a ways off.  (And anyways, cross
    #     compilers probably have a dedicated binary with the
    #     right paths compiled in.  I hope.)
    #   * can't do really freaky things with the library list/library
    #     dirs, e.g. "-Ldir1 -lfoo -Ldir2 -lfoo" to link against
    #     different versions of libfoo.a in different locations.  I
    #     think this is useless without the ability to null out the
    #     library search path anyways.

    # Subclasses that rely on the standard filename generation methods
    # implemented below should override these; see the comment near
    # those methods ('object_filenames()' et. al.) for details:
    src_extensions = None  # list of strings
    obj_extension = None  # string
    static_lib_extension = None
    shared_lib_extension = None  # string
    static_lib_format = None  # format string
    shared_lib_format = None  # prob. same as static_lib_format
    exe_extension = None  # string

    # Default language settings. language_map is used to detect a source
    # file or Extension target language, checking source filenames.
    # language_order is used to detect the language precedence, when deciding
    # what language to use when mixing source types. For example, if some
    # extension has two files with ".c" extension, and one with ".cpp", it
    # is still linked as c++.
    language_map = {
        ".c": "c",
        ".cc": "c++",
        ".cpp": "c++",
        ".cxx": "c++",
        ".m": "objc",
    }
    language_order = ["c++", "objc", "c"]

    include_dirs = []
    """
    include dirs specific to this compiler class
    """

    library_dirs = []
    """
    library dirs specific to this compiler class
    """

    def __init__(self, verbose=False, dry_run=False, force=False):
        self.dry_run = dry_run
        self.force = force
        self.verbose = verbose

        # 'output_dir': a common output directory for object, library,
        # shared object, and shared library files
        self.output_dir = None

        # 'macros': a list of macro definitions (or undefinitions).  A
        # macro definition is a 2-tuple (name, value), where the value is
        # either a string or None (no explicit value).  A macro
        # undefinition is a 1-tuple (name,).
        self.macros = []

        # 'include_dirs': a list of directories to search for include files
        self.include_dirs = []

        # 'libraries': a list of libraries to include in any link
        # (library names, not filenames: eg. "foo" not "libfoo.a")
        self.libraries = []

        # 'library_dirs': a list of directories to search for libraries
        self.library_dirs = []

        # 'runtime_library_dirs': a list of directories to search for
        # shared libraries/objects at runtime
        self.runtime_library_dirs = []

        # 'objects': a list of object files (or similar, such as explicitly
        # named library files) to include on any link
        self.objects = []

        for key in self.executables.keys():
            self.set_executable(key, self.executables[key])

    def set_executables(self, **kwargs):
        """Define the executables (and options for them) that will be run
        to perform the various stages of compilation.  The exact set of
        executables that may be specified here depends on the compiler
        class (via the 'executables' class attribute), but most will have:
          compiler      the C/C++ compiler
          linker_so     linker used to create shared objects and libraries
          linker_exe    linker used to create binary executables
          archiver      static library creator

        On platforms with a command-line (Unix, DOS/Windows), each of these
        is a string that will be split into executable name and (optional)
        list of arguments.  (Splitting the string is done similarly to how
        Unix shells operate: words are delimited by spaces, but quotes and
        backslashes can override this.  See
        'distutils.util.split_quoted()'.)
        """

        # Note that some CCompiler implementation classes will define class
        # attributes 'cpp', 'cc', etc. with hard-coded executable names;
        # this is appropriate when a compiler class is for exactly one
        # compiler/OS combination (eg. MSVCCompiler).  Other compiler
        # classes (UnixCCompiler, in particular) are driven by information
        # discovered at run-time, since there are many different ways to do
        # basically the same things with Unix C compilers.

        for key in kwargs:
            if key not in self.executables:
                raise ValueError(
                    f"unknown executable '{key}' for class {self.__class__.__name__}"
                )
            self.set_executable(key, kwargs[key])

    def set_executable(self, key, value):
        if isinstance(value, str):
            setattr(self, key, split_quoted(value))
        else:
            setattr(self, key, value)

    def _find_macro(self, name):
        i = 0
        for defn in self.macros:
            if defn[0] == name:
                return i
            i += 1
        return None

    def _check_macro_definitions(self, definitions):
        """Ensure that every element of 'definitions' is valid."""
        for defn in definitions:
            self._check_macro_definition(*defn)

    def _check_macro_definition(self, defn):
        """
        Raise a TypeError if defn is not valid.

        A valid definition is either a (name, value) 2-tuple or a (name,) tuple.
        """
        if not isinstance(defn, tuple) or not self._is_valid_macro(*defn):
            raise TypeError(
                f"invalid macro definition '{defn}': "
                "must be tuple (string,), (string, string), or (string, None)"
            )

    @staticmethod
    def _is_valid_macro(name, value=None):
        """
        A valid macro is a ``name : str`` and a ``value : str | None``.
        """
        return isinstance(name, str) and isinstance(value, (str, types.NoneType))

    # -- Bookkeeping methods -------------------------------------------

    def define_macro(self, name, value=None):
        """Define a preprocessor macro for all compilations driven by this
        compiler object.  The optional parameter 'value' should be a
        string; if it is not supplied, then the macro will be defined
        without an explicit value and the exact outcome depends on the
        compiler used (XXX true? does ANSI say anything about this?)
        """
        # Delete from the list of macro definitions/undefinitions if
        # already there (so that this one will take precedence).
        i = self._find_macro(name)
        if i is not None:
            del self.macros[i]

        self.macros.append((name, value))

    def undefine_macro(self, name):
        """Undefine a preprocessor macro for all compilations driven by
        this compiler object.  If the same macro is defined by
        'define_macro()' and undefined by 'undefine_macro()' the last call
        takes precedence (including multiple redefinitions or
        undefinitions).  If the macro is redefined/undefined on a
        per-compilation basis (ie. in the call to 'compile()'), then that
        takes precedence.
        """
        # Delete from the list of macro definitions/undefinitions if
        # already there (so that this one will take precedence).
        i = self._find_macro(name)
        if i is not None:
            del self.macros[i]

        undefn = (name,)
        self.macros.append(undefn)

    def add_include_dir(self, dir):
        """Add 'dir' to the list of directories that will be searched for
        header files.  The compiler is instructed to search directories in
        the order in which they are supplied by successive calls to
        'add_include_dir()'.
        """
        self.include_dirs.append(dir)

    def set_include_dirs(self, dirs):
        """Set the list of directories that will be searched to 'dirs' (a
        list of strings).  Overrides any preceding calls to
        'add_include_dir()'; subsequence calls to 'add_include_dir()' add
        to the list passed to 'set_include_dirs()'.  This does not affect
        any list of standard include directories that the compiler may
        search by default.
        """
        self.include_dirs = dirs[:]

    def add_library(self, libname):
        """Add 'libname' to the list of libraries that will be included in
        all links driven by this compiler object.  Note that 'libname'
        should *not* be the name of a file containing a library, but the
        name of the library itself: the actual filename will be inferred by
        the linker, the compiler, or the compiler class (depending on the
        platform).

        The linker will be instructed to link against libraries in the
        order they were supplied to 'add_library()' and/or
        'set_libraries()'.  It is perfectly valid to duplicate library
        names; the linker will be instructed to link against libraries as
        many times as they are mentioned.
        """
        self.libraries.append(libname)

    def set_libraries(self, libnames):
        """Set the list of libraries to be included in all links driven by
        this compiler object to 'libnames' (a list of strings).  This does
        not affect any standard system libraries that the linker may
        include by default.
        """
        self.libraries = libnames[:]

    def add_library_dir(self, dir):
        """Add 'dir' to the list of directories that will be searched for
        libraries specified to 'add_library()' and 'set_libraries()'.  The
        linker will be instructed to search for libraries in the order they
        are supplied to 'add_library_dir()' and/or 'set_library_dirs()'.
        """
        self.library_dirs.append(dir)

    def set_library_dirs(self, dirs):
        """Set the list of library search directories to 'dirs' (a list of
        strings).  This does not affect any standard library search path
        that the linker may search by default.
        """
        self.library_dirs = dirs[:]

    def add_runtime_library_dir(self, dir):
        """Add 'dir' to the list of directories that will be searched for
        shared libraries at runtime.
        """
        self.runtime_library_dirs.append(dir)

    def set_runtime_library_dirs(self, dirs):
        """Set the list of directories to search for shared libraries at
        runtime to 'dirs' (a list of strings).  This does not affect any
        standard search path that the runtime linker may search by
        default.
        """
        self.runtime_library_dirs = dirs[:]

    def add_link_object(self, object):
        """Add 'object' to the list of object files (or analogues, such as
        explicitly named library files or the output of "resource
        compilers") to be included in every link driven by this compiler
        object.
        """
        self.objects.append(object)

    def set_link_objects(self, objects):
        """Set the list of object files (or analogues) to be included in
        every link to 'objects'.  This does not affect any standard object
        files that the linker may include by default (such as system
        libraries).
        """
        self.objects = objects[:]

    # -- Private utility methods --------------------------------------
    # (here for the convenience of subclasses)

    # Helper method to prep compiler in subclass compile() methods

    def _setup_compile(self, outdir, macros, incdirs, sources, depends, extra):
        """Process arguments and decide which source files to compile."""
        outdir, macros, incdirs = self._fix_compile_args(outdir, macros, incdirs)

        if extra is None:
            extra = []

        # Get the list of expected output (object) files
        objects = self.object_filenames(sources, strip_dir=False, output_dir=outdir)
        assert len(objects) == len(sources)

        pp_opts = gen_preprocess_options(macros, incdirs)

        build = {}
        for i in range(len(sources)):
            src = sources[i]
            obj = objects[i]
            ext = os.path.splitext(src)[1]
            self.mkpath(os.path.dirname(obj))
            build[obj] = (src, ext)

        return macros, objects, extra, pp_opts, build

    def _get_cc_args(self, pp_opts, debug, before):
        # works for unixccompiler, cygwinccompiler
        cc_args = pp_opts + ['-c']
        if debug:
            cc_args[:0] = ['-g']
        if before:
            cc_args[:0] = before
        return cc_args

    def _fix_compile_args(self, output_dir, macros, include_dirs):
        """Typecheck and fix-up some of the arguments to the 'compile()'
        method, and return fixed-up values.  Specifically: if 'output_dir'
        is None, replaces it with 'self.output_dir'; ensures that 'macros'
        is a list, and augments it with 'self.macros'; ensures that
        'include_dirs' is a list, and augments it with 'self.include_dirs'.
        Guarantees that the returned values are of the correct type,
        i.e. for 'output_dir' either string or None, and for 'macros' and
        'include_dirs' either list or None.
        """
        if output_dir is None:
            output_dir = self.output_dir
        elif not isinstance(output_dir, str):
            raise TypeError("'output_dir' must be a string or None")

        if macros is None:
            macros = list(self.macros)
        elif isinstance(macros, list):
            macros = macros + (self.macros or [])
        else:
            raise TypeError("'macros' (if supplied) must be a list of tuples")

        if include_dirs is None:
            include_dirs = list(self.include_dirs)
        elif isinstance(include_dirs, (list, tuple)):
            include_dirs = list(include_dirs) + (self.include_dirs or [])
        else:
            raise TypeError("'include_dirs' (if supplied) must be a list of strings")

        # add include dirs for class
        include_dirs += self.__class__.include_dirs

        return output_dir, macros, include_dirs

    def _prep_compile(self, sources, output_dir, depends=None):
        """Decide which source files must be recompiled.

        Determine the list of object files corresponding to 'sources',
        and figure out which ones really need to be recompiled.
        Return a list of all object files and a dictionary telling
        which source files can be skipped.
        """
        # Get the list of expected output (object) files
        objects = self.object_filenames(sources, output_dir=output_dir)
        assert len(objects) == len(sources)

        # Return an empty dict for the "which source files can be skipped"
        # return value to preserve API compatibility.
        return objects, {}

    def _fix_object_args(self, objects, output_dir):
        """Typecheck and fix up some arguments supplied to various methods.
        Specifically: ensure that 'objects' is a list; if output_dir is
        None, replace with self.output_dir.  Return fixed versions of
        'objects' and 'output_dir'.
        """
        if not isinstance(objects, (list, tuple)):
            raise TypeError("'objects' must be a list or tuple of strings")
        objects = list(objects)

        if output_dir is None:
            output_dir = self.output_dir
        elif not isinstance(output_dir, str):
            raise TypeError("'output_dir' must be a string or None")

        return (objects, output_dir)

    def _fix_lib_args(self, libraries, library_dirs, runtime_library_dirs):
        """Typecheck and fix up some of the arguments supplied to the
        'link_*' methods.  Specifically: ensure that all arguments are
        lists, and augment them with their permanent versions
        (eg. 'self.libraries' augments 'libraries').  Return a tuple with
        fixed versions of all arguments.
        """
        if libraries is None:
            libraries = list(self.libraries)
        elif isinstance(libraries, (list, tuple)):
            libraries = list(libraries) + (self.libraries or [])
        else:
            raise TypeError("'libraries' (if supplied) must be a list of strings")

        if library_dirs is None:
            library_dirs = list(self.library_dirs)
        elif isinstance(library_dirs, (list, tuple)):
            library_dirs = list(library_dirs) + (self.library_dirs or [])
        else:
            raise TypeError("'library_dirs' (if supplied) must be a list of strings")

        # add library dirs for class
        library_dirs += self.__class__.library_dirs

        if runtime_library_dirs is None:
            runtime_library_dirs = list(self.runtime_library_dirs)
        elif isinstance(runtime_library_dirs, (list, tuple)):
            runtime_library_dirs = list(runtime_library_dirs) + (
                self.runtime_library_dirs or []
            )
        else:
            raise TypeError(
                "'runtime_library_dirs' (if supplied) must be a list of strings"
            )

        return (libraries, library_dirs, runtime_library_dirs)

    def _need_link(self, objects, output_file):
        """Return true if we need to relink the files listed in 'objects'
        to recreate 'output_file'.
        """
        if self.force:
            return True
        else:
            if self.dry_run:
                newer = newer_group(objects, output_file, missing='newer')
            else:
                newer = newer_group(objects, output_file)
            return newer

    def detect_language(self, sources):
        """Detect the language of a given file, or list of files. Uses
        language_map, and language_order to do the job.
        """
        if not isinstance(sources, list):
            sources = [sources]
        lang = None
        index = len(self.language_order)
        for source in sources:
            base, ext = os.path.splitext(source)
            extlang = self.language_map.get(ext)
            try:
                extindex = self.language_order.index(extlang)
                if extindex < index:
                    lang = extlang
                    index = extindex
            except ValueError:
                pass
        return lang

    # -- Worker methods ------------------------------------------------
    # (must be implemented by subclasses)

    def preprocess(
        self,
        source,
        output_file=None,
        macros=None,
        include_dirs=None,
        extra_preargs=None,
        extra_postargs=None,
    ):
        """Preprocess a single C/C++ source file, named in 'source'.
        Output will be written to file named 'output_file', or stdout if
        'output_file' not supplied.  'macros' is a list of macro
        definitions as for 'compile()', which will augment the macros set
        with 'define_macro()' and 'undefine_macro()'.  'include_dirs' is a
        list of directory names that will be added to the default list.

        Raises PreprocessError on failure.
        """
        pass

    def compile(
        self,
        sources,
        output_dir=None,
        macros=None,
        include_dirs=None,
        debug=False,
        extra_preargs=None,
        extra_postargs=None,
        depends=None,
    ):
        """Compile one or more source files.

        'sources' must be a list of filenames, most likely C/C++
        files, but in reality anything that can be handled by a
        particular compiler and compiler class (eg. MSVCCompiler can
        handle resource files in 'sources').  Return a list of object
        filenames, one per source filename in 'sources'.  Depending on
        the implementation, not all source files will necessarily be
        compiled, but all corresponding object filenames will be
        returned.

        If 'output_dir' is given, object files will be put under it, while
        retaining their original path component.  That is, "foo/bar.c"
        normally compiles to "foo/bar.o" (for a Unix implementation); if
        'output_dir' is "build", then it would compile to
        "build/foo/bar.o".

        'macros', if given, must be a list of macro definitions.  A macro
        definition is either a (name, value) 2-tuple or a (name,) 1-tuple.
        The former defines a macro; if the value is None, the macro is
        defined without an explicit value.  The 1-tuple case undefines a
        macro.  Later definitions/redefinitions/ undefinitions take
        precedence.

        'include_dirs', if given, must be a list of strings, the
        directories to add to the default include file search path for this
        compilation only.

        'debug' is a boolean; if true, the compiler will be instructed to
        output debug symbols in (or alongside) the object file(s).

        'extra_preargs' and 'extra_postargs' are implementation- dependent.
        On platforms that have the notion of a command-line (e.g. Unix,
        DOS/Windows), they are most likely lists of strings: extra
        command-line arguments to prepend/append to the compiler command
        line.  On other platforms, consult the implementation class
        documentation.  In any event, they are intended as an escape hatch
        for those occasions when the abstract compiler framework doesn't
        cut the mustard.

        'depends', if given, is a list of filenames that all targets
        depend on.  If a source file is older than any file in
        depends, then the source file will be recompiled.  This
        supports dependency tracking, but only at a coarse
        granularity.

        Raises CompileError on failure.
        """
        # A concrete compiler class can either override this method
        # entirely or implement _compile().
        macros, objects, extra_postargs, pp_opts, build = self._setup_compile(
            output_dir, macros, include_dirs, sources, depends, extra_postargs
        )
        cc_args = self._get_cc_args(pp_opts, debug, extra_preargs)

        for obj in objects:
            try:
                src, ext = build[obj]
            except KeyError:
                continue
            self._compile(obj, src, ext, cc_args, extra_postargs, pp_opts)

        # Return *all* object filenames, not just the ones we just built.
        return objects

    def _compile(self, obj, src, ext, cc_args, extra_postargs, pp_opts):
        """Compile 'src' to product 'obj'."""
        # A concrete compiler class that does not override compile()
        # should implement _compile().
        pass

    def create_static_lib(
        self, objects, output_libname, output_dir=None, debug=False, target_lang=None
    ):
        """Link a bunch of stuff together to create a static library file.
        The "bunch of stuff" consists of the list of object files supplied
        as 'objects', the extra object files supplied to
        'add_link_object()' and/or 'set_link_objects()', the libraries
        supplied to 'add_library()' and/or 'set_libraries()', and the
        libraries supplied as 'libraries' (if any).

        'output_libname' should be a library name, not a filename; the
        filename will be inferred from the library name.  'output_dir' is
        the directory where the library file will be put.

        'debug' is a boolean; if true, debugging information will be
        included in the library (note that on most platforms, it is the
        compile step where this matters: the 'debug' flag is included here
        just for consistency).

        'target_lang' is the target language for which the given objects
        are being compiled. This allows specific linkage time treatment of
        certain languages.

        Raises LibError on failure.
        """
        pass

    # values for target_desc parameter in link()
    SHARED_OBJECT = "shared_object"
    SHARED_LIBRARY = "shared_library"
    EXECUTABLE = "executable"

    def link(
        self,
        target_desc,
        objects,
        output_filename,
        output_dir=None,
        libraries=None,
        library_dirs=None,
        runtime_library_dirs=None,
        export_symbols=None,
        debug=False,
        extra_preargs=None,
        extra_postargs=None,
        build_temp=None,
        target_lang=None,
    ):
        """Link a bunch of stuff together to create an executable or
        shared library file.

        The "bunch of stuff" consists of the list of object files supplied
        as 'objects'.  'output_filename' should be a filename.  If
        'output_dir' is supplied, 'output_filename' is relative to it
        (i.e. 'output_filename' can provide directory components if
        needed).

        'libraries' is a list of libraries to link against.  These are
        library names, not filenames, since they're translated into
        filenames in a platform-specific way (eg. "foo" becomes "libfoo.a"
        on Unix and "foo.lib" on DOS/Windows).  However, they can include a
        directory component, which means the linker will look in that
        specific directory rather than searching all the normal locations.

        'library_dirs', if supplied, should be a list of directories to
        search for libraries that were specified as bare library names
        (ie. no directory component).  These are on top of the system
        default and those supplied to 'add_library_dir()' and/or
        'set_library_dirs()'.  'runtime_library_dirs' is a list of
        directories that will be embedded into the shared library and used
        to search for other shared libraries that *it* depends on at
        run-time.  (This may only be relevant on Unix.)

        'export_symbols' is a list of symbols that the shared library will
        export.  (This appears to be relevant only on Windows.)

        'debug' is as for 'compile()' and 'create_static_lib()', with the
        slight distinction that it actually matters on most platforms (as
        opposed to 'create_static_lib()', which includes a 'debug' flag
        mostly for form's sake).

        'extra_preargs' and 'extra_postargs' are as for 'compile()' (except
        of course that they supply command-line arguments for the
        particular linker being used).

        'target_lang' is the target language for which the given objects
        are being compiled. This allows specific linkage time treatment of
        certain languages.

        Raises LinkError on failure.
        """
        raise NotImplementedError

    # Old 'link_*()' methods, rewritten to use the new 'link()' method.

    def link_shared_lib(
        self,
        objects,
        output_libname,
        output_dir=None,
        libraries=None,
        library_dirs=None,
        runtime_library_dirs=None,
        export_symbols=None,
        debug=False,
        extra_preargs=None,
        extra_postargs=None,
        build_temp=None,
        target_lang=None,
    ):
        self.link(
            CCompiler.SHARED_LIBRARY,
            objects,
            self.library_filename(output_libname, lib_type='shared'),
            output_dir,
            libraries,
            library_dirs,
            runtime_library_dirs,
            export_symbols,
            debug,
            extra_preargs,
            extra_postargs,
            build_temp,
            target_lang,
        )

    def link_shared_object(
        self,
        objects,
        output_filename,
        output_dir=None,
        libraries=None,
        library_dirs=None,
        runtime_library_dirs=None,
        export_symbols=None,
        debug=False,
        extra_preargs=None,
        extra_postargs=None,
        build_temp=None,
        target_lang=None,
    ):
        self.link(
            CCompiler.SHARED_OBJECT,
            objects,
            output_filename,
            output_dir,
            libraries,
            library_dirs,
            runtime_library_dirs,
            export_symbols,
            debug,
            extra_preargs,
            extra_postargs,
            build_temp,
            target_lang,
        )

    def link_executable(
        self,
        objects,
        output_progname,
        output_dir=None,
        libraries=None,
        library_dirs=None,
        runtime_library_dirs=None,
        debug=False,
        extra_preargs=None,
        extra_postargs=None,
        target_lang=None,
    ):
        self.link(
            CCompiler.EXECUTABLE,
            objects,
            self.executable_filename(output_progname),
            output_dir,
            libraries,
            library_dirs,
            runtime_library_dirs,
            None,
            debug,
            extra_preargs,
            extra_postargs,
            None,
            target_lang,
        )

    # -- Miscellaneous methods -----------------------------------------
    # These are all used by the 'gen_lib_options() function; there is
    # no appropriate default implementation so subclasses should
    # implement all of these.

    def library_dir_option(self, dir):
        """Return the compiler option to add 'dir' to the list of
        directories searched for libraries.
        """
        raise NotImplementedError

    def runtime_library_dir_option(self, dir):
        """Return the compiler option to add 'dir' to the list of
        directories searched for runtime libraries.
        """
        raise NotImplementedError

    def library_option(self, lib):
        """Return the compiler option to add 'lib' to the list of libraries
        linked into the shared library or executable.
        """
        raise NotImplementedError

    def has_function(  # noqa: C901
        self,
        funcname,
        includes=None,
        include_dirs=None,
        libraries=None,
        library_dirs=None,
    ):
        """Return a boolean indicating whether funcname is provided as
        a symbol on the current platform.  The optional arguments can
        be used to augment the compilation environment.

        The libraries argument is a list of flags to be passed to the
        linker to make additional symbol definitions available for
        linking.

        The includes and include_dirs arguments are deprecated.
        Usually, supplying include files with function declarations
        will cause function detection to fail even in cases where the
        symbol is available for linking.

        """
        # this can't be included at module scope because it tries to
        # import math which might not be available at that point - maybe
        # the necessary logic should just be inlined?
        import tempfile

        if includes is None:
            includes = []
        else:
            warnings.warn("includes is deprecated", DeprecationWarning)
        if include_dirs is None:
            include_dirs = []
        else:
            warnings.warn("include_dirs is deprecated", DeprecationWarning)
        if libraries is None:
            libraries = []
        if library_dirs is None:
            library_dirs = []
        fd, fname = tempfile.mkstemp(".c", funcname, text=True)
        with os.fdopen(fd, "w", encoding='utf-8') as f:
            for incl in includes:
                f.write(f"""#include "{incl}"\n""")
            if not includes:
                # Use "char func(void);" as the prototype to follow
                # what autoconf does.  This prototype does not match
                # any well-known function the compiler might recognize
                # as a builtin, so this ends up as a true link test.
                # Without a fake prototype, the test would need to
                # know the exact argument types, and the has_function
                # interface does not provide that level of information.
                f.write(
                    f"""\
#ifdef __cplusplus
extern "C"
#endif
char {funcname}(void);
"""
                )
            f.write(
                f"""\
int main (int argc, char **argv) {{
    {funcname}();
    return 0;
}}
"""
            )

        try:
            objects = self.compile([fname], include_dirs=include_dirs)
        except CompileError:
            return False
        finally:
            os.remove(fname)

        try:
            self.link_executable(
                objects, "a.out", libraries=libraries, library_dirs=library_dirs
            )
        except (LinkError, TypeError):
            return False
        else:
            os.remove(
                self.executable_filename("a.out", output_dir=self.output_dir or '')
            )
        finally:
            for fn in objects:
                os.remove(fn)
        return True

    def find_library_file(self, dirs, lib, debug=False):
        """Search the specified list of directories for a static or shared
        library file 'lib' and return the full path to that file.  If
        'debug' true, look for a debugging version (if that makes sense on
        the current platform).  Return None if 'lib' wasn't found in any of
        the specified directories.
        """
        raise NotImplementedError

    # -- Filename generation methods -----------------------------------

    # The default implementation of the filename generating methods are
    # prejudiced towards the Unix/DOS/Windows view of the world:
    #   * object files are named by replacing the source file extension
    #     (eg. .c/.cpp -> .o/.obj)
    #   * library files (shared or static) are named by plugging the
    #     library name and extension into a format string, eg.
    #     "lib%s.%s" % (lib_name, ".a") for Unix static libraries
    #   * executables are named by appending an extension (possibly
    #     empty) to the program name: eg. progname + ".exe" for
    #     Windows
    #
    # To reduce redundant code, these methods expect to find
    # several attributes in the current object (presumably defined
    # as class attributes):
    #   * src_extensions -
    #     list of C/C++ source file extensions, eg. ['.c', '.cpp']
    #   * obj_extension -
    #     object file extension, eg. '.o' or '.obj'
    #   * static_lib_extension -
    #     extension for static library files, eg. '.a' or '.lib'
    #   * shared_lib_extension -
    #     extension for shared library/object files, eg. '.so', '.dll'
    #   * static_lib_format -
    #     format string for generating static library filenames,
    #     eg. 'lib%s.%s' or '%s.%s'
    #   * shared_lib_format
    #     format string for generating shared library filenames
    #     (probably same as static_lib_format, since the extension
    #     is one of the intended parameters to the format string)
    #   * exe_extension -
    #     extension for executable files, eg. '' or '.exe'

    def object_filenames(self, source_filenames, strip_dir=False, output_dir=''):
        if output_dir is None:
            output_dir = ''
        return list(
            self._make_out_path(output_dir, strip_dir, src_name)
            for src_name in source_filenames
        )

    @property
    def out_extensions(self):
        return dict.fromkeys(self.src_extensions, self.obj_extension)

    def _make_out_path(self, output_dir, strip_dir, src_name):
        return self._make_out_path_exts(
            output_dir, strip_dir, src_name, self.out_extensions
        )

    @classmethod
    def _make_out_path_exts(cls, output_dir, strip_dir, src_name, extensions):
        r"""
        >>> exts = {'.c': '.o'}
        >>> CCompiler._make_out_path_exts('.', False, '/foo/bar.c', exts).replace('\\', '/')
        './foo/bar.o'
        >>> CCompiler._make_out_path_exts('.', True, '/foo/bar.c', exts).replace('\\', '/')
        './bar.o'
        """
        src = pathlib.PurePath(src_name)
        # Ensure base is relative to honor output_dir (python/cpython#37775).
        base = cls._make_relative(src)
        try:
            new_ext = extensions[src.suffix]
        except LookupError:
            raise UnknownFileError(f"unknown file type '{src.suffix}' (from '{src}')")
        if strip_dir:
            base = pathlib.PurePath(base.name)
        return os.path.join(output_dir, base.with_suffix(new_ext))

    @staticmethod
    def _make_relative(base: pathlib.Path):
        return base.relative_to(base.anchor)

    def shared_object_filename(self, basename, strip_dir=False, output_dir=''):
        assert output_dir is not None
        if strip_dir:
            basename = os.path.basename(basename)
        return os.path.join(output_dir, basename + self.shared_lib_extension)

    def executable_filename(self, basename, strip_dir=False, output_dir=''):
        assert output_dir is not None
        if strip_dir:
            basename = os.path.basename(basename)
        return os.path.join(output_dir, basename + (self.exe_extension or ''))

    def library_filename(
        self,
        libname,
        lib_type='static',
        strip_dir=False,
        output_dir='',  # or 'shared'
    ):
        assert output_dir is not None
        expected = '"static", "shared", "dylib", "xcode_stub"'
        if lib_type not in eval(expected):
            raise ValueError(f"'lib_type' must be {expected}")
        fmt = getattr(self, lib_type + "_lib_format")
        ext = getattr(self, lib_type + "_lib_extension")

        dir, base = os.path.split(libname)
        filename = fmt % (base, ext)
        if strip_dir:
            dir = ''

        return os.path.join(output_dir, dir, filename)

    # -- Utility methods -----------------------------------------------

    def announce(self, msg, level=1):
        log.debug(msg)

    def debug_print(self, msg):
        from setuptools._distutils.debug import DEBUG

        if DEBUG:
            print(msg)

    def warn(self, msg):
        sys.stderr.write(f"warning: {msg}\n")

    def execute(self, func, args, msg=None, level=1):
        execute(func, args, msg, self.dry_run)

    def spawn(self, cmd, **kwargs):
        spawn(cmd, dry_run=self.dry_run, **kwargs)

    def move_file(self, src, dst):
        return move_file(src, dst, dry_run=self.dry_run)

    def mkpath(self, name, mode=0o777):
        mkpath(name, mode, dry_run=self.dry_run)


# Map a sys.platform/os.name ('posix', 'nt') to the default compiler
# type for that platform. Keys are interpreted as re match
# patterns. Order is important; platform mappings are preferred over
# OS names.
_default_compilers = (
    # Platform string mappings
    # on a cygwin built python we can use gcc like an ordinary UNIXish
    # compiler
    ('cygwin.*', 'unix'),
    ('zos', 'zos'),
    # OS name mappings
    ('posix', 'unix'),
    ('nt', 'msvc'),
)


def get_default_compiler(osname=None, platform=None):
    """Determine the default compiler to use for the given platform.

    osname should be one of the standard Python OS names (i.e. the
    ones returned by os.name) and platform the common value
    returned by sys.platform for the platform in question.

    The default values are os.name and sys.platform in case the
    parameters are not given.
    """
    if osname is None:
        osname = os.name
    if platform is None:
        platform = sys.platform
    # Mingw is a special case where sys.platform is 'win32' but we
    # want to use the 'mingw32' compiler, so check it first
    if is_mingw():
        return 'mingw32'
    for pattern, compiler in _default_compilers:
        if (
            re.match(pattern, platform) is not None
            or re.match(pattern, osname) is not None
        ):
            return compiler
    # Default to Unix compiler
    return 'unix'


# Map compiler types to (module_name, class_name) pairs -- ie. where to
# find the code that implements an interface to this compiler.  (The module
# is assumed to be in the 'distutils' package.)
compiler_class = {
    'unix': ('unixccompiler', 'UnixCCompiler', "standard UNIX-style compiler"),
    'msvc': ('_msvccompiler', 'MSVCCompiler', "Microsoft Visual C++"),
    'cygwin': (
        'cygwinccompiler',
        'CygwinCCompiler',
        "Cygwin port of GNU C Compiler for Win32",
    ),
    'mingw32': (
        'cygwinccompiler',
        'Mingw32CCompiler',
        "Mingw32 port of GNU C Compiler for Win32",
    ),
    'bcpp': ('bcppcompiler', 'BCPPCompiler', "Borland C++ Compiler"),
    'zos': ('zosccompiler', 'zOSCCompiler', 'IBM XL C/C++ Compilers'),
}


def show_compilers():
    """Print list of available compilers (used by the "--help-compiler"
    options to "build", "build_ext", "build_clib").
    """
    # XXX this "knows" that the compiler option it's describing is
    # "--compiler", which just happens to be the case for the three
    # commands that use it.
    from setuptools._distutils.fancy_getopt import FancyGetopt

    compilers = sorted(
        ("compiler=" + compiler, None, compiler_class[compiler][2])
        for compiler in compiler_class.keys()
    )
    pretty_printer = FancyGetopt(compilers)
    pretty_printer.print_help("List of available compilers:")


def new_compiler(plat=None, compiler=None, verbose=False, dry_run=False, force=False):
    """Generate an instance of some CCompiler subclass for the supplied
    platform/compiler combination.  'plat' defaults to 'os.name'
    (eg. 'posix', 'nt'), and 'compiler' defaults to the default compiler
    for that platform.  Currently only 'posix' and 'nt' are supported, and
    the default compilers are "traditional Unix interface" (UnixCCompiler
    class) and Visual C++ (MSVCCompiler class).  Note that it's perfectly
    possible to ask for a Unix compiler object under Windows, and a
    Microsoft compiler object under Unix -- if you supply a value for
    'compiler', 'plat' is ignored.
    """
    if plat is None:
        plat = os.name

    try:
        if compiler is None:
            compiler = get_default_compiler(plat)

        (module_name, class_name, long_description) = compiler_class[compiler]
    except KeyError:
        msg = f"don't know how to compile C/C++ code on platform '{plat}'"
        if compiler is not None:
            msg = msg + f" with '{compiler}' compiler"
        raise PlatformError(msg)

    try:
        module_name = "distutils." + module_name
        __import__(module_name)
        module = sys.modules[module_name]
        klass = vars(module)[class_name]
    except ImportError:
        raise ModuleError(
            f"can't compile C/C++ code: unable to load module '{module_name}'"
        )
    except KeyError:
        raise ModuleError(
            f"can't compile C/C++ code: unable to find class '{class_name}' "
            f"in module '{module_name}'"
        )

    # XXX The None is necessary to preserve backwards compatibility
    # with classes that expect verbose to be the first positional
    # argument.
    return klass(None, dry_run, force)


def gen_preprocess_options(macros, include_dirs):
    """Generate C pre-processor options (-D, -U, -I) as used by at least
    two types of compilers: the typical Unix compiler and Visual C++.
    'macros' is the usual thing, a list of 1- or 2-tuples, where (name,)
    means undefine (-U) macro 'name', and (name,value) means define (-D)
    macro 'name' to 'value'.  'include_dirs' is just a list of directory
    names to be added to the header file search path (-I).  Returns a list
    of command-line options suitable for either Unix compilers or Visual
    C++.
    """
    # XXX it would be nice (mainly aesthetic, and so we don't generate
    # stupid-looking command lines) to go over 'macros' and eliminate
    # redundant definitions/undefinitions (ie. ensure that only the
    # latest mention of a particular macro winds up on the command
    # line).  I don't think it's essential, though, since most (all?)
    # Unix C compilers only pay attention to the latest -D or -U
    # mention of a macro on their command line.  Similar situation for
    # 'include_dirs'.  I'm punting on both for now.  Anyways, weeding out
    # redundancies like this should probably be the province of
    # CCompiler, since the data structures used are inherited from it
    # and therefore common to all CCompiler classes.
    pp_opts = []
    for macro in macros:
        if not (isinstance(macro, tuple) and 1 <= len(macro) <= 2):
            raise TypeError(
                f"bad macro definition '{macro}': "
                "each element of 'macros' list must be a 1- or 2-tuple"
            )

        if len(macro) == 1:  # undefine this macro
            pp_opts.append(f"-U{macro[0]}")
        elif len(macro) == 2:
            if macro[1] is None:  # define with no explicit value
                pp_opts.append(f"-D{macro[0]}")
            else:
                # XXX *don't* need to be clever about quoting the
                # macro value here, because we're going to avoid the
                # shell at all costs when we spawn the command!
                pp_opts.append("-D{}={}".format(*macro))

    pp_opts.extend(f"-I{dir}" for dir in include_dirs)
    return pp_opts


def gen_lib_options(compiler, library_dirs, runtime_library_dirs, libraries):
    """Generate linker options for searching library directories and
    linking with specific libraries.  'libraries' and 'library_dirs' are,
    respectively, lists of library names (not filenames!) and search
    directories.  Returns a list of command-line options suitable for use
    with some compiler (depending on the two format strings passed in).
    """
    lib_opts = [compiler.library_dir_option(dir) for dir in library_dirs]

    for dir in runtime_library_dirs:
        lib_opts.extend(always_iterable(compiler.runtime_library_dir_option(dir)))

    # XXX it's important that we *not* remove redundant library mentions!
    # sometimes you really do have to say "-lfoo -lbar -lfoo" in order to
    # resolve all symbols.  I just hope we never have to say "-lfoo obj.o
    # -lbar" to get things to work -- that's certainly a possibility, but a
    # pretty nasty way to arrange your C code.

    for lib in libraries:
        (lib_dir, lib_name) = os.path.split(lib)
        if lib_dir:
            lib_file = compiler.find_library_file([lib_dir], lib_name)
            if lib_file:
                lib_opts.append(lib_file)
            else:
                compiler.warn(
                    f"no library file corresponding to '{lib}' found (skipping)"
                )
        else:
            lib_opts.append(compiler.library_option(lib))
    return lib_opts


class config(Command):

    description = "prepare to build"

    user_options = [
        ('compiler=', None,
         "specify the compiler type"),
        ('cc=', None,
         "specify the compiler executable"),
        ('include-dirs=', 'I',
         "list of directories to search for header files"),
        ('define=', 'D',
         "C preprocessor macros to define"),
        ('undef=', 'U',
         "C preprocessor macros to undefine"),
        ('libraries=', 'l',
         "external C libraries to link with"),
        ('library-dirs=', 'L',
         "directories to search for external C libraries"),

        ('noisy', None,
         "show every action (compile, link, run, ...) taken"),
        ('dump-source', None,
         "dump generated source files before attempting to compile them"),
        ]


    # The three standard command methods: since the "config" command
    # does nothing by default, these are empty.

    def initialize_options(self):
        self.compiler = None
        self.cc = None
        self.include_dirs = None
        self.libraries = None
        self.library_dirs = None

        # maximal output for now
        self.noisy = 1
        self.dump_source = 1

        # list of temporary files generated along-the-way that we have
        # to clean at some point
        self.temp_files = []

    def finalize_options(self):
        if self.include_dirs is None:
            self.include_dirs = self.distribution.include_dirs or []
        elif isinstance(self.include_dirs, str):
            self.include_dirs = self.include_dirs.split(os.pathsep)

        if self.libraries is None:
            self.libraries = []
        elif isinstance(self.libraries, str):
            self.libraries = [self.libraries]

        if self.library_dirs is None:
            self.library_dirs = []
        elif isinstance(self.library_dirs, str):
            self.library_dirs = self.library_dirs.split(os.pathsep)

    def run(self):
        pass

    # Utility methods for actual "config" commands.  The interfaces are
    # loosely based on Autoconf macros of similar names.  Sub-classes
    # may use these freely.

    def _check_compiler(self):
        """Check that 'self.compiler' really is a CCompiler object;
        if not, make it one.
        """
        # We do this late, and only on-demand, because this is an expensive
        # import.
        from distutils.ccompiler import CCompiler, new_compiler
        if not isinstance(self.compiler, CCompiler):
            self.compiler = new_compiler(compiler=self.compiler,
                                         dry_run=self.dry_run, force=1)
            customize_compiler(self.compiler)
            if self.include_dirs:
                self.compiler.set_include_dirs(self.include_dirs)
            if self.libraries:
                self.compiler.set_libraries(self.libraries)
            if self.library_dirs:
                self.compiler.set_library_dirs(self.library_dirs)

    def _gen_temp_sourcefile(self, body, headers, lang):
        filename = "_configtest" + LANG_EXT[lang]
        with open(filename, "w") as file:
            if headers:
                for header in headers:
                    file.write("#include <%s>\n" % header)
                file.write("\n")
            file.write(body)
            if body[-1] != "\n":
                file.write("\n")
        return filename

    def _preprocess(self, body, headers, include_dirs, lang):
        src = self._gen_temp_sourcefile(body, headers, lang)
        out = "_configtest.i"
        self.temp_files.extend([src, out])
        self.compiler.preprocess(src, out, include_dirs=include_dirs)
        return (src, out)

    def _compile(self, body, headers, include_dirs, lang):
        src = self._gen_temp_sourcefile(body, headers, lang)
        if self.dump_source:
            dump_file(src, "compiling '%s':" % src)
        (obj,) = self.compiler.object_filenames([src])
        self.temp_files.extend([src, obj])
        self.compiler.compile([src], include_dirs=include_dirs)
        return (src, obj)

    def _link(self, body, headers, include_dirs, libraries, library_dirs,
              lang):
        (src, obj) = self._compile(body, headers, include_dirs, lang)
        prog = os.path.splitext(os.path.basename(src))[0]
        self.compiler.link_executable([obj], prog,
                                      libraries=libraries,
                                      library_dirs=library_dirs,
                                      target_lang=lang)

        if self.compiler.exe_extension is not None:
            prog = prog + self.compiler.exe_extension
        self.temp_files.append(prog)

        return (src, obj, prog)

    def _clean(self, *filenames):
        if not filenames:
            filenames = self.temp_files
            self.temp_files = []
        log.info("removing: %s", ' '.join(filenames))
        for filename in filenames:
            try:
                os.remove(filename)
            except OSError:
                pass


    # XXX these ignore the dry-run flag: what to do, what to do? even if
    # you want a dry-run build, you still need some sort of configuration
    # info.  My inclination is to make it up to the real config command to
    # consult 'dry_run', and assume a default (minimal) configuration if
    # true.  The problem with trying to do it here is that you'd have to
    # return either true or false from all the 'try' methods, neither of
    # which is correct.

    # XXX need access to the header search path and maybe default macros.

    def try_cpp(self, body=None, headers=None, include_dirs=None, lang="c"):
        """Construct a source file from 'body' (a string containing lines
        of C/C++ code) and 'headers' (a list of header files to include)
        and run it through the preprocessor.  Return true if the
        preprocessor succeeded, false if there were any errors.
        ('body' probably isn't of much use, but what the heck.)
        """
        self._check_compiler()
        ok = True
        try:
            self._preprocess(body, headers, include_dirs, lang)
        except CompileError:
            ok = False

        self._clean()
        return ok

    def search_cpp(self, pattern, body=None, headers=None, include_dirs=None,
                   lang="c"):
        """Construct a source file (just like 'try_cpp()'), run it through
        the preprocessor, and return true if any line of the output matches
        'pattern'.  'pattern' should either be a compiled regex object or a
        string containing a regex.  If both 'body' and 'headers' are None,
        preprocesses an empty file -- which can be useful to determine the
        symbols the preprocessor and compiler set by default.
        """
        self._check_compiler()
        src, out = self._preprocess(body, headers, include_dirs, lang)

        if isinstance(pattern, str):
            pattern = re.compile(pattern)

        with open(out) as file:
            match = False
            while True:
                line = file.readline()
                if line == '':
                    break
                if pattern.search(line):
                    match = True
                    break

        self._clean()
        return match

    def try_compile(self, body, headers=None, include_dirs=None, lang="c"):
        """Try to compile a source file built from 'body' and 'headers'.
        Return true on success, false otherwise.
        """

        self._check_compiler()
        try:
            self._compile(body, headers, include_dirs, lang)
            ok = True
        except CompileError:
            ok = False

        log.info(ok and "success!" or "failure.")
        self._clean()
        return ok

    def try_link(self, body, headers=None, include_dirs=None, libraries=None,
                 library_dirs=None, lang="c"):
        """Try to compile and link a source file, built from 'body' and
        'headers', to executable form.  Return true on success, false
        otherwise.
        """
        self._check_compiler()
        try:
            self._link(body, headers, include_dirs,
                       libraries, library_dirs, lang)
            ok = True
        except (CompileError, LinkError):
            ok = False

        log.info(ok and "success!" or "failure.")
        self._clean()
        return ok

    def try_run(self, body, headers=None, include_dirs=None, libraries=None,
                library_dirs=None, lang="c"):
        """Try to compile, link to an executable, and run a program
        built from 'body' and 'headers'.  Return true on success, false
        otherwise.
        """
        self._check_compiler()
        try:
            src, obj, exe = self._link(body, headers, include_dirs,
                                       libraries, library_dirs, lang)
            self.spawn([exe])
            ok = True
        except (CompileError, LinkError, ExecError):
            ok = False

        log.info(ok and "success!" or "failure.")
        self._clean()
        return ok


    # -- High-level methods --------------------------------------------
    # (these are the ones that are actually likely to be useful
    # when implementing a real-world config command!)

    def check_func(self, func, headers=None, include_dirs=None,
                   libraries=None, library_dirs=None, decl=0, call=0):
        """Determine if function 'func' is available by constructing a
        source file that refers to 'func', and compiles and links it.
        If everything succeeds, returns true; otherwise returns false.

        The constructed source file starts out by including the header
        files listed in 'headers'.  If 'decl' is true, it then declares
        'func' (as "int func()"); you probably shouldn't supply 'headers'
        and set 'decl' true in the same call, or you might get errors about
        a conflicting declarations for 'func'.  Finally, the constructed
        'main()' function either references 'func' or (if 'call' is true)
        calls it.  'libraries' and 'library_dirs' are used when
        linking.
        """
        self._check_compiler()
        body = []
        if decl:
            body.append("int %s ();" % func)
        body.append("int main () {")
        if call:
            body.append("  %s();" % func)
        else:
            body.append("  %s;" % func)
        body.append("}")
        body = "\n".join(body) + "\n"

        return self.try_link(body, headers, include_dirs,
                             libraries, library_dirs)

    def check_lib(self, library, library_dirs=None, headers=None,
                  include_dirs=None, other_libraries=[]):
        """Determine if 'library' is available to be linked against,
        without actually checking that any particular symbols are provided
        by it.  'headers' will be used in constructing the source file to
        be compiled, but the only effect of this is to check if all the
        header files listed are available.  Any libraries listed in
        'other_libraries' will be included in the link, in case 'library'
        has symbols that depend on other libraries.
        """
        self._check_compiler()
        return self.try_link("int main (void) { }", headers, include_dirs,
                             [library] + other_libraries, library_dirs)

    def check_header(self, header, include_dirs=None, library_dirs=None,
                     lang="c"):
        """Determine if the system header file named by 'header_file'
        exists and can be found by the preprocessor; return true if so,
        false otherwise.
        """
        return self.try_cpp(body="/* No body */", headers=[header],
                            include_dirs=include_dirs)

def dump_file(filename, head=None):
    """Dumps a file content into log.info.

    If head is not None, will be dumped before the file content.
    """
    if head is None:
        log.info('%s', filename)
    else:
        log.info(head)
    file = open(filename)
    try:
        log.info(file.read())
    finally:
        file.close()
