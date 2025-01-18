import pytest
from mbpy.pkg.docparse2 import CharClass, Pattern, get_char_class, analyze_line, analyze_document

def test_char_class_constants():
    assert CharClass.ALPHA_UPPER == 'alpha_upper'
    assert CharClass.ALPHA_LOWER == 'alpha_lower'
    assert CharClass.INDENT == 'indent'
    assert CharClass.NUMERIC == 'numeric'
    assert CharClass.PERIOD == 'period'
    assert CharClass.BULLET == 'bullet'
    assert CharClass.COLON == 'colon'
    assert CharClass.SEMICOLON == 'semicolon'
    assert CharClass.SYMBOL == 'symbol'
    assert CharClass.PARENTHESIS == 'parenthesis'
    assert CharClass.BRACKET == 'bracket'
    assert CharClass.QUOTE == 'quote'
    assert CharClass.WHITESPACE == 'whitespace'

def test_pattern_class():
    pattern = Pattern()
    assert pattern.horizontal_classes == []
    assert pattern.vertical_classes == []
    
    pattern.add_horizontal('test_class', 3)
    assert pattern.horizontal_classes == [('test_class', 3)]
    
    pattern.add_vertical(2, 1)
    assert pattern.vertical_classes == [(2, 1)]

def test_get_char_class():
    assert get_char_class('A') == CharClass.ALPHA_UPPER
    assert get_char_class('a') == CharClass.ALPHA_LOWER
    assert get_char_class(' ') == CharClass.INDENT
    assert get_char_class('5') == CharClass.NUMERIC
    assert get_char_class('.') == CharClass.PERIOD
    assert get_char_class('-') == CharClass.BULLET
    assert get_char_class('*') == CharClass.BULLET
    assert get_char_class('•') == CharClass.BULLET
    assert get_char_class(':') == CharClass.COLON
    assert get_char_class(';') == CharClass.SEMICOLON
    assert get_char_class('@') is None

def test_get_char_class_extended():
    # Test special characters
    assert get_char_class('!') == CharClass.SYMBOL
    assert get_char_class('(') == CharClass.PARENTHESIS
    assert get_char_class('[') == CharClass.BRACKET
    assert get_char_class('"') == CharClass.QUOTE
    assert get_char_class('\t') == CharClass.WHITESPACE
    assert get_char_class('●') == CharClass.BULLET
    assert get_char_class('&') == CharClass.SYMBOL

def test_analyze_line():
    # Test basic line analysis
    line = "  Hello 123."
    pattern = analyze_line(line)
    
    assert pattern.vertical_classes == [(2, 1)]
    assert pattern.horizontal_classes == [
        (CharClass.INDENT, 2),
        (CharClass.ALPHA_UPPER, 1),
        (CharClass.ALPHA_LOWER, 4),
        (CharClass.INDENT, 1),
        (CharClass.NUMERIC, 3),
        (CharClass.PERIOD, 1)
    ]

def test_analyze_line_general_text():
    test_cases = [
        # Complex line with mixed content
        ("Hello, world! (test) [123]", [
            (CharClass.ALPHA_UPPER, 1),
            (CharClass.ALPHA_LOWER, 4),
            (CharClass.SYMBOL, 2),
            (CharClass.INDENT, 1),
            (CharClass.ALPHA_LOWER, 5),
            (CharClass.SYMBOL, 1),
            (CharClass.INDENT, 1),
            (CharClass.PARENTHESIS, 1),
            (CharClass.ALPHA_LOWER, 4),
            (CharClass.PARENTHESIS, 1),
            (CharClass.INDENT, 1),
            (CharClass.BRACKET, 1),
            (CharClass.NUMERIC, 3),
            (CharClass.BRACKET, 1),
        ]),
        
        # Line with special characters
        ("***Bold*** `code`", [
            (CharClass.BULLET, 3),
            (CharClass.ALPHA_LOWER, 4),
            (CharClass.BULLET, 3),
            (CharClass.INDENT, 1),
            (CharClass.QUOTE, 1),
            (CharClass.ALPHA_LOWER, 4),
            (CharClass.QUOTE, 1),
        ]),
    ]
    
    for input_line, expected_classes in test_cases:
        pattern = analyze_line(input_line)
        assert pattern.horizontal_classes == expected_classes

def test_analyze_document():
    document = [
        "Title",
        "  * Item 1",
        "  * Item 2",
        "    - Subitem"
    ]
    
    patterns = analyze_document(document)
    
    # Check number of patterns
    assert len(patterns) == 4
    
    # Check first line (Title)
    assert patterns[0].vertical_classes == [(0, 1)]
    
    # Check indented items
    assert patterns[1].vertical_classes == [(0, 1), (2, 2)]
    assert patterns[2].vertical_classes == [(0, 1), (2, 2)]
    
    # Check subitem
    assert patterns[3].vertical_classes == [(0, 1), (2, 2), (4, 1)]

def test_analyze_document_general():
    document = [
        "# Header",
        "Normal text with (parentheses) and [brackets]",
        "  * List item with **bold**",
        "    1. Numbered item",
        "```",
        "code block",
        "```"
    ]
    
    patterns = analyze_document(document)
    assert len(patterns) == 7
    
    # Test different indent levels are captured
    assert patterns[0].vertical_classes == [(0, 1)]
    assert patterns[2].vertical_classes == [(2, 1)]
    assert patterns[3].vertical_classes == [(4, 1)]

def test_analyze_uv_help():
    from rich.tree import Tree
    from rich.console import Console

    help_text = """Usage: uv [OPTIONS] <COMMAND>

Commands:
  run      Run a command or script
  init     Create a new project
  add      Add dependencies to the project
  remove   Remove dependencies from the project
  sync     Update the project's environment
  lock     Update the project's lockfile
  export   Export the project's lockfile to an alternate format
  tree     Display the project's dependency tree
  tool     Run and install commands provided by Python packages
  python   Manage Python versions and installations
  pip      Manage Python packages with a pip-compatible interface
  venv     Create a virtual environment
  build    Build Python packages into source distributions and wheels
  publish  Upload distributions to an index
  cache    Manage uv's cache
  self     Manage the uv executable
  version  Display uv's version
  help     Display documentation for a command

Cache options:
  -n, --no-cache               Avoid reading from or writing to the cache, instead using a temporary directory for the duration of the operation [env: UV_NO_CACHE=]
      --cache-dir <CACHE_DIR>  Path to the cache directory [env: UV_CACHE_DIR=]

Python options:
      --python-preference <PYTHON_PREFERENCE>  Whether to prefer uv-managed or system Python installations [env: UV_PYTHON_PREFERENCE=] [possible values: only-managed, managed,
                                               system, only-system]
      --no-python-downloads                    Disable automatic downloads of Python. [env: "UV_PYTHON_DOWNLOADS=never"]

Global options:
  -q, --quiet                                      Do not print any output
  -v, --verbose...                                 Use verbose output
      --color <COLOR_CHOICE>                       Control colors in output [default: auto] [possible values: auto, always, never]
      --native-tls                                 Whether to load TLS certificates from the platform's native certificate store [env: UV_NATIVE_TLS=]
      --offline                                    Disable network access
      --allow-insecure-host <ALLOW_INSECURE_HOST>  Allow insecure connections to a host [env: UV_INSECURE_HOST=]
      --no-progress                                Hide all progress outputs [env: UV_NO_PROGRESS=]
      --directory <DIRECTORY>                      Change to the given directory prior to running the command
      --project <PROJECT>                          Run the command within the given project directory
      --config-file <CONFIG_FILE>                  The path to a `uv.toml` file to use for configuration [env: UV_CONFIG_FILE=]
      --no-config                                  Avoid discovering configuration files (`pyproject.toml`, `uv.toml`) [env: UV_NO_CONFIG=]
  -h, --help                                       Display the concise help for this command
  -V, --version                                    Display the uv version

Use `uv help` for more details."""

    # Parse the document
    lines = help_text.split('\n')
    patterns = analyze_document(lines)

    # Create rich tree
    console = Console()
    root = Tree("🔧 UV CLI")

    current_section = None
    for i, (line, pattern) in enumerate(zip(lines, patterns)):
        line = line.strip()
        if not line:
            continue
            
        # Detect main sections by checking if next line has more indentation
        if i < len(lines) - 1 and len(line) > 0:
            if line.endswith(':'):  # Section header like "Commands:"
                current_section = root.add(f"[bold blue]{line}[/]")
            elif current_section and pattern.vertical_classes:
                # Split command and description
                parts = line.split(maxsplit=1)
                if len(parts) == 2:
                    cmd, desc = parts
                    current_section.add(f"[green]{cmd:<12}[/] {desc}")
                else:
                    current_section.add(line)
            else:
                # Top level items
                root.add(line)

    # Display the tree
    console.print(root)

if __name__ == '__main__':
    pytest.main(['-v', '-s'])

