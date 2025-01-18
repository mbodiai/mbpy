import pytest
from mbpy.docparser import DocumentProcessor, OutputFormat
from mbpy.chars import CharClass, get_char_class
from mbpy.grammar import GrammarProcessor, Pattern

@pytest.fixture
def cli_docs():
    return """
Usage: uv [OPTIONS] <COMMAND>

Commands:
  run      Run a command or script
  init     Create a new project
  add      Add dependencies to the project
  
Cache options:
  -n, --no-cache     Avoid reading from or writing to the cache
  --cache-dir <DIR>  Path to the cache directory
"""

def test_task_structure_parsing():
    # Test input with correct type syntax
    test_input = """
dependency_graph: Task[None] = {
    "name": "Test Task",
    "context": "Test Context",
    "subtasks": []
}
"""
    # Test DocumentProcessor
    doc_processor = DocumentProcessor()
    classifications = doc_processor.process_document(test_input)
    
    # Basic assertions for DocumentProcessor
    assert len(classifications) > 0
    root_class = classifications[0]
    assert root_class.pattern_type == "text"  # Should start with 'dependency_graph'
    
    # Check pattern recognition using GrammarProcessor
    processor = GrammarProcessor()
    patterns = processor.analyze_patterns(test_input)
    level_0_patterns = patterns.get(0, [])
    assert len(level_0_patterns) > 0
    
    # Check for braces in first non-empty line
    first_pattern = next((p for p in level_0_patterns if p.line.strip()), None)
    assert first_pattern is not None
    
    has_braces = any(
        class_ in (CharClass.ENCLOSER_OPEN, CharClass.ENCLOSER_CLOSE)
        for class_, _ in first_pattern.horizontal
    )
    assert has_braces, "Failed to detect enclosers"

    # Test nested structure
    level_1_patterns = patterns.get(1, [])
    assert len(level_1_patterns) > 0, "Should detect nested structure"

def test_docparser_detailed_output():
    """Test detailed output formatting with explicit expected outputs"""
    test_input = 'test_var: str = "test"'
    
    # Expected JSON output
    expected_json = """\
{
  "type": "variable",
  "content": "test_var: str = \\"test\\"",
  "level": 0,
  "attributes": {
    "name": "test_var",
    "type": "str",
    "value": "\\"test\\""
  },
  "lines": {"start": 1, "end": 1},
  "children": []
}"""

    # Expected Markdown output  
    expected_markdown = """\
<details>
<summary>test_var: str = "test" (Line 1)</summary>

- **test_var: str = "test"**
  - Outer Class: `lower_alpha`
  - Inner Group: `1`
</details>"""

    doc_processor = DocumentProcessor()
    json_result = doc_processor.format_output(
        doc_processor.process_document(test_input),
        OutputFormat.JSON
    )
    assert json_result.strip() == expected_json.strip()

    md_result = doc_processor.format_output(
        doc_processor.process_document(test_input),
        OutputFormat.MARKDOWN  
    )
    assert md_result.strip() == expected_markdown.strip()

def test_complex_type_parsing():
    """Test parsing complex type expressions with explicit expected outputs"""
    test_inputs = [
        'simple: str = "test"',
        'list_type: List[int] = [1, 2, 3]', 
        'nested: Dict[str, List[int]] = {"a": [1, 2]}',
        'none_type: Optional[str] = None'
    ]

    expected_outputs = [
        {
            "line": 'simple: str = "test"',
            "pattern_type": "variable",
            "attributes": {
                "name": "simple",
                "type": "str",
                "value": '"test"'
            }
        },
        {
            "line": 'list_type: List[int] = [1, 2, 3]',
            "pattern_type": "variable", 
            "attributes": {
                "name": "list_type",
                "type": "List[int]",
                "value": "[1, 2, 3]"
            }
        },
        {
            "line": 'nested: Dict[str, List[int]] = {"a": [1, 2]}',
            "pattern_type": "variable",
            "attributes": {
                "name": "nested", 
                "type": "Dict[str, List[int]]",
                "value": '{"a": [1, 2]}'
            }
        },
        {
            "line": 'none_type: Optional[str] = None',
            "pattern_type": "variable",
            "attributes": {
                "name": "none_type",
                "type": "Optional[str]", 
                "value": "None"
            }
        }
    ]

    doc_processor = DocumentProcessor()
    for input_text, expected in zip(test_inputs, expected_outputs):
        result = doc_processor.process_document(input_text)[0]
        assert result.content == expected["line"]
        assert result.pattern_type == expected["pattern_type"]
        assert result.attributes == expected["attributes"]

def test_char_classification():
    """Test character classification system"""
    assert get_char_class('{') == CharClass.ENCLOSER_OPEN
    assert get_char_class('}') == CharClass.ENCLOSER_CLOSE
    assert get_char_class('"') == CharClass.QUOTE
    assert get_char_class('A') == CharClass.ALPHA_UPPER
    assert get_char_class('a') == CharClass.ALPHA_LOWER
    assert get_char_class('1') == CharClass.NUMERIC
    assert get_char_class('#') == CharClass.HASH

def test_pattern_analysis():
    """Test pattern analysis capabilities"""
    test_input = """
def example():
    first_block = 1
    second_block = 2
    
    # Another block
    third_block = 3
    fourth_block = 4
    
    if True:
        nested = True
        deeply = True
"""
    processor = GrammarProcessor()
    patterns = processor.analyze_patterns(test_input)
    
    # Level 1 patterns (4-space indentation)
    level_1_starts = processor.get_level_starts(1)
    
    # Filter out empty lines and combine similar blocks
    actual_blocks = [
        block for block in level_1_starts 
        if block[0].strip() and not block[0].strip().startswith('#')
    ]
    assert len(actual_blocks) == 3, f"Expected 3 distinct blocks, got {len(actual_blocks)}: {actual_blocks}"
    
    # Level 2 patterns (8-space indentation)
    level_2_starts = processor.get_level_starts(2)
    assert len(level_2_starts) == 1, "Should have one nested block"

def test_pattern_repetition():
    """Test detection of repeating patterns at different levels"""
    test_input = """
# Level 0 - Headers and metadata
Title: My Document
Author: John Doe
Date: 2024-01-01

# Level 0 - Section with repeating structure
* Item 1
* Item 2
* Item 3

# Level 1 - Indented blocks with similar structure
    def function1():
        return 1
    
    def function2():
        return 2
        
    def function3():
        return 3

# Level 1 - Different pattern
    # Comments in a block
    # More comments here
    # And more comments
"""
    processor = GrammarProcessor()
    patterns = processor.analyze_patterns(test_input)
    
    # Level 0 patterns
    level_0 = patterns.get(0, [])
    metadata_pattern = next(p for p in level_0 if "Title:" in p.line)
    assert metadata_pattern.horizontal[0][0] == CharClass.ALPHA_UPPER
    
    # Check bullet point pattern
    bullet_patterns = [p for p in level_0 if p.line.strip().startswith('*')]
    assert len(bullet_patterns) == 3
    assert all(p.horizontal[0][0] == CharClass.BULLET for p in bullet_patterns)
    
    # Level 1 patterns - function definitions
    level_1 = patterns.get(1, [])
    function_patterns = [p for p in level_1 if 'def' in p.line]
    assert len(function_patterns) == 3
    assert all(len(p.horizontal) >= 3 for p in function_patterns)  # def keyword + name + ()
    
    # Comment block pattern
    comment_patterns = [p for p in level_1 if p.line.strip().startswith('#')]
    assert len(comment_patterns) == 3
    assert all(p.horizontal[0][0] == CharClass.HASH for p in comment_patterns)

def test_horizontal_class_sequence():
    """Test sequence of character classes within a line"""
    test_input = """
def example(): -> str
    x: int = 123
    y: List[int] = [1, 2, 3]
    result = {"key": value}
"""
    processor = GrammarProcessor()
    patterns = processor.analyze_patterns(test_input)
    
    # Function definition line
    func_def = patterns[0][0]  # First line pattern
    expected_classes = [
        CharClass.ALPHA_LOWER,  # def
        CharClass.ALPHA_LOWER,  # example
        CharClass.ENCLOSER_OPEN,  # (
        CharClass.ENCLOSER_CLOSE,  # )
        CharClass.OPERATOR,  # ->
        CharClass.ALPHA_LOWER,  # str
    ]
    assert [h[0] for h in func_def.horizontal] == expected_classes

    # Variable assignment with type annotation
    var_def = patterns[0][1]  # Second line pattern
    assert var_def.horizontal[0][0] == CharClass.ALPHA_LOWER  # x
    assert var_def.horizontal[1][0] == CharClass.SEPARATOR    # :
    assert var_def.horizontal[2][0] == CharClass.ALPHA_LOWER  # int

def test_cli_docs_patterns(cli_docs):
    """Test pattern analysis on CLI documentation"""
    processor = GrammarProcessor()
    patterns = processor.analyze_patterns(cli_docs)
    
    # Example blocks we expect to find:
    
    # 1. Command block pattern
    command_patterns = [
        p for p in patterns.get(1, [])
        if p.line.strip().startswith('run') or p.line.strip().startswith('init')
    ]
    print("\nCommand Block Pattern:")
    for p in command_patterns[:2]:
        print(f"Line {p.line_number}: {p.line.strip()}")
        print(f"Horizontal: {[(c.__name__, n) for c, n in p.horizontal]}")
    
    # 2. Option block pattern
    option_patterns = [
        p for p in patterns.get(1, [])
        if p.line.strip().startswith('-') or p.line.strip().startswith('--')
    ]
    print("\nOption Block Pattern:")
    for p in option_patterns[:2]:
        print(f"Line {p.line_number}: {p.line.strip()}")
        print(f"Horizontal: {[(c.__name__, n) for c, n in p.horizontal]}")
    
    # 3. Description block pattern
    desc_patterns = [
        p for p in patterns.get(2, [])  # One level deeper
        if len(p.line.strip()) > 0 and not p.line.strip().startswith('-')
    ]
    print("\nDescription Block Pattern:")
    for p in desc_patterns[:2]:
        print(f"Line {p.line_number}: {p.line.strip()}")
        print(f"Horizontal: {[(c.__name__, n) for c, n in p.horizontal]}")
    
    # Assertions for structure
    assert len(command_patterns) > 0, "Should find command patterns"
    assert len(option_patterns) > 0, "Should find option patterns"
    assert len(desc_patterns) > 0, "Should find description patterns"
    
    # Test pattern grouping
    level_1_starts = processor.get_level_starts(1)
    print("\nLevel 1 Block Starts:")
    for line, num in level_1_starts[:5]:
        print(f"Line {num}: {line.strip()}")
        
    # Group by sections
    sections = {
        "Commands": [p for p in patterns.get(0, []) if "Commands:" in p.line],
        "Options": [p for p in patterns.get(0, []) if "options:" in p.line.lower()],
    }
    print("\nMain Sections:")
    for section, patterns_list in sections.items():
        print(f"\n{section}:")
        for p in patterns_list:
            print(f"Line {p.line_number}: {p.line.strip()}")

def test_pattern_block_examples():
    """Test different types of pattern blocks"""
    test_cases = [
        # 1. Command Block
        """
        command subcommand [OPTIONS]
            --flag      Flag description
            --option    Option description
        """,
        
        # 2. List Block
        """
        * First item
        * Second item
        * Third item
        """,
        
        # 3. Indented Block
        """
        def function():
            first line
            second line
            third line
        """,
        
        # 4. Mixed Block
        """
        Title:
            - Point 1
            - Point 2
                * Subpoint A
                * Subpoint B
        """
    ]
    
    processor = GrammarProcessor()
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}:")
        patterns = processor.analyze_patterns(test_case)
        
        for level, level_patterns in patterns.items():
            print(f"\nLevel {level}:")
            for p in level_patterns:
                if p.line.strip():
                    print(f"Line {p.line_number}: {p.line.strip()}")
                    print(f"Horizontal: {[(c.__name__, n) for c, n in p.horizontal]}")
                    print(f"Vertical: {p.vertical}")

def test_repetition_patterns():
    """Test detection of repeating patterns"""
    test_input = """
    # Simple list
    * Item 1
    * Item 2
    * Item 3
    
    # Numbered list
    1. First
    2. Second
    3. Third
    
    # Mixed indentation
        - Level 1
            * Level 2a
            * Level 2b
        - Level 1 again
            * Level 2c
            * Level 2d
    """
    
    processor = GrammarProcessor()
    patterns = processor.analyze_patterns(test_input)
    
    print("\nRepetition Patterns:")
    for level, level_patterns in patterns.items():
        contiguous = []
        current = []
        
        for p in level_patterns:
            if not current or processor._is_similar_pattern(current[-1], p):
                current.append(p)
            else:
                if len(current) > 1:
                    contiguous.append(current)
                current = [p]
        
        if len(current) > 1:
            contiguous.append(current)
            
        for i, block in enumerate(contiguous):
            print(f"\nRepeating Block {i+1} at Level {level}:")
            for p in block:
                print(f"Line {p.line_number}: {p.line.strip()}")
                print(f"Pattern: {[(c.__name__, n) for c, n in p.horizontal]}")

def test_basic_pattern_blocks():
    """Test basic pattern detection with explicit outputs"""
    test_case = """
def example():
    return True
"""
    expected_patterns = [
        Pattern(
            horizontal=[(CharClass.ALPHA_LOWER, 3), (CharClass.ALPHA_LOWER, 7), 
                       (CharClass.ENCLOSER_OPEN, 1), (CharClass.ENCLOSER_CLOSE, 1)],
            vertical=[(0, 1)],
            line="def example():",
            line_number=2
        ),
        Pattern(
            horizontal=[(CharClass.ALPHA_LOWER, 6), (CharClass.ALPHA_UPPER, 4)],
            vertical=[(1, 1)],
            line="    return True",
            line_number=3
        )
    ]
    
    processor = GrammarProcessor()
    patterns = processor.analyze_patterns(test_case)
    
    assert patterns[0][0].horizontal == expected_patterns[0].horizontal
    assert patterns[1][0].horizontal == expected_patterns[1].horizontal

def test_repeating_patterns():
    """Test detection of repeating structures with explicit outputs"""
    test_case = """
* First item
* Second item
* Third item
"""
    expected_output = """
Pattern Block at Level 0:
Line 2: * First item
Horizontal: [(BULLET, 1), (ALPHA_UPPER, 5), (WHITESPACE, 1), (ALPHA_LOWER, 4)]
Line 3: * Second item
Horizontal: [(BULLET, 1), (ALPHA_UPPER, 6), (WHITESPACE, 1), (ALPHA_LOWER, 4)]
Line 4: * Third item
Horizontal: [(BULLET, 1), (ALPHA_UPPER, 5), (WHITESPACE, 1), (ALPHA_LOWER, 4)]
"""
    processor = GrammarProcessor()
    patterns = processor.analyze_patterns(test_case)
    
    output = []
    output.append("Pattern Block at Level 0:")
    for p in patterns[0]:
        output.append(f"Line {p.line_number}: {p.line.strip()}")
        output.append(f"Horizontal: {[(c.__name__, n) for c, n in p.horizontal]}")
    
    assert "\n".join(output) == expected_output.strip()

def test_cli_command_block():
    """Test CLI command block pattern detection"""
    test_case = """
Commands:
  run      Run a command or script
  init     Create a new project
  add      Add dependencies
"""
    expected_output = {
        'header': 'Commands:',
        'commands': [
            ('run', 'Run a command or script'),
            ('init', 'Create a new project'),
            ('add', 'Add dependencies')
        ]
    }
    
    processor = GrammarProcessor()
    patterns = processor.analyze_patterns(test_case)
    
    # Extract commands and their descriptions
    level_1 = patterns.get(1, [])
    commands = [
        (p.line.strip().split()[0], ' '.join(p.line.strip().split()[1:]))
        for p in level_1
    ]
    
    result = {
        'header': patterns[0][0].line.strip(),
        'commands': commands
    }
    
    assert result == expected_output

def test_option_block_pattern():
    """Test option block pattern with expected whitespace alignment"""
    test_case = """
Options:
  -h, --help     Show help message
  -v, --version  Show version
"""
    expected_structure = [
        {'indent': 0, 'type': 'header', 'text': 'Options:'},
        {'indent': 2, 'type': 'option', 'short': '-h', 'long': '--help', 
         'desc': 'Show help message'},
        {'indent': 2, 'type': 'option', 'short': '-v', 'long': '--version',
         'desc': 'Show version'}
    ]
    
    processor = GrammarProcessor()
    patterns = processor.analyze_patterns(test_case)
    
    result = []
    for level, level_patterns in patterns.items():
        for p in level_patterns:
            line = p.line.strip()
            if level == 0:
                result.append({
                    'indent': level,
                    'type': 'header',
                    'text': line
                })
            else:
                if line.startswith('-'):
                    parts = line.split(None, 2)
                    result.append({
                        'indent': level,
                        'type': 'option',
                        'short': parts[0].rstrip(','),
                        'long': parts[1],
                        'desc': parts[2]
                    })
    
    assert result == expected_structure

def test_cli_docs_structure(cli_docs):
    """Test CLI docs pattern analysis with exact expected output"""
    processor = GrammarProcessor()
    patterns = processor.analyze_patterns(cli_docs)
    
    expected_output = """
Command Block Pattern:
Line 5: run      Run a command or script
Horizontal: [(ALPHA_LOWER, 3), (WHITESPACE, 6), (ALPHA_UPPER, 3), (WHITESPACE, 1), (ALPHA_LOWER, 7)]
Line 6: init     Create a new project
Horizontal: [(ALPHA_LOWER, 4), (WHITESPACE, 5), (ALPHA_UPPER, 6), (WHITESPACE, 1), (ALPHA_LOWER, 3)]

Option Block Pattern:
Line 23: -n, --no-cache               Avoid reading from or writing to the cache
Horizontal: [(OPERATOR, 1), (ALPHA_LOWER, 1), (SEPARATOR, 1), (WHITESPACE, 1), (OPERATOR, 2), (ALPHA_LOWER, 8)]
Line 24: --cache-dir <CACHE_DIR>  Path to the cache directory
Horizontal: [(OPERATOR, 2), (ALPHA_LOWER, 9), (WHITESPACE, 1), (ENCLOSER_OPEN, 1), (ALPHA_UPPER, 9), (ENCLOSER_CLOSE, 1)]
"""
    
    # Generate actual output
    output = []
    output.append("Command Block Pattern:")
    for p in list(patterns.get(1, []))[:2]:  # First two commands
        if p.line.strip().startswith(('run', 'init')):
            output.append(f"Line {p.line_number}: {p.line.strip()}")
            output.append(f"Horizontal: {[(c.__name__, n) for c, n in p.horizontal]}")
    
    output.append("\nOption Block Pattern:")
    for p in list(patterns.get(1, []))[:2]:  # First two options
        if p.line.strip().startswith('-'):
            output.append(f"Line {p.line_number}: {p.line.strip()}")
            output.append(f"Horizontal: {[(c.__name__, n) for c, n in p.horizontal]}")
    
    assert "\n".join(output) == expected_output.strip()

def test_repeating_block_patterns():
    """Test repeating block pattern detection with exact output"""
    test_input = """
* First item
* Second item
* Third item
"""
    expected_output = """
Level 0 Patterns:
Line 2: * First item
Pattern: [(BULLET, 1), (ALPHA_UPPER, 5), (ALPHA_LOWER, 4)]
Line 3: * Second item
Pattern: [(BULLET, 1), (ALPHA_UPPER, 6), (ALPHA_LOWER, 4)]
Line 4: * Third item
Pattern: [(BULLET, 1), (ALPHA_UPPER, 5), (ALPHA_LOWER, 4)]
"""
    
    processor = GrammarProcessor()
    patterns = processor.analyze_patterns(test_input)
    
    output = []
    output.append("Level 0 Patterns:")
    for p in patterns.get(0, []):
        if p.line.strip():
            output.append(f"Line {p.line_number}: {p.line.strip()}")
            output.append(f"Pattern: {[(c.__name__, n) for c, n in p.horizontal]}")
    
    assert "\n".join(output) == expected_output.strip()

def test_indented_block_pattern():
    """Test indented block pattern detection with exact output"""
    test_input = """
def example():
    first = 1
    second = 2
"""
    expected_output = """
Block Structure:
Level 0:
Line 2: def example():
Pattern: [(ALPHA_LOWER, 3), (WHITESPACE, 1), (ALPHA_LOWER, 7), (ENCLOSER_OPEN, 1), (ENCLOSER_CLOSE, 1)]

Level 1:
Line 3:     first = 1
Pattern: [(ALPHA_LOWER, 5), (WHITESPACE, 1), (OPERATOR, 1), (WHITESPACE, 1), (NUMERIC, 1)]
Line 4:     second = 2
Pattern: [(ALPHA_LOWER, 6), (WHITESPACE, 1), (OPERATOR, 1), (WHITESPACE, 1), (NUMERIC, 1)]
"""
    
    processor = GrammarProcessor()
    patterns = processor.analyze_patterns(test_input)
    
    output = []
    output.append("Block Structure:")
    for level in sorted(patterns.keys()):
        output.append(f"Level {level}:")
        for p in patterns[level]:
            if p.line.strip():
                output.append(f"Line {p.line_number}: {p.line.strip()}")
                output.append(f"Pattern: {[(c.__name__, n) for c, n in p.horizontal]}")
        output.append("")
    
    assert "\n".join(output).strip() == expected_output.strip()

def test_markdown_output():
    """Test markdown output formatting with exact expected output"""
    test_input = """
def example():
    return True
"""
    expected_output = """\
<details>
<summary>def example(): (Line 2)</summary>

- **def example():**
  - Outer Class: `lower_alpha`
  - Inner Group: `2`

<details>
<summary>Sub-Classifications</summary>

    <details>
    <summary>    return True (Line 3)</summary>

    - **return True**
      - Outer Class: `lower_alpha`
      - Inner Group: `3`
    </details>

</details>
</details>"""
    
    doc_processor = DocumentProcessor()
    result = doc_processor.format_output(
        doc_processor.process_document(test_input),
        OutputFormat.MARKDOWN
    )
    
    assert result.strip() == expected_output.strip()

def test_json_output():
    """Test JSON output formatting with exact expected output"""
    test_input = "example = 42"
    expected_output = """{
  "line": "example = 42",
  "line_number": 1,
  "depth": 0,
  "outer_class": "lower_alpha",
  "inner_group": 1,
  "sub_classifications": []
}"""
    
    doc_processor = DocumentProcessor()
    result = doc_processor.format_output(
        doc_processor.process_document(test_input),
        OutputFormat.JSON
    )
    
    assert result.strip() == expected_output.strip()

def test_cli_command_pattern(cli_docs):
    """Test command pattern detection with exact output"""
    processor = GrammarProcessor()
    patterns = processor.analyze_patterns(cli_docs)
    
    expected_output = {
        "level_0": {
            "sections": ["Usage:", "Commands:", "Cache options:"],
            "patterns": [
                [(CharClass.ALPHA_UPPER, 1), (CharClass.ALPHA_LOWER, 4)],  # Usage
                [(CharClass.ALPHA_UPPER, 1), (CharClass.ALPHA_LOWER, 7)],  # Commands
                [(CharClass.ALPHA_UPPER, 1), (CharClass.ALPHA_LOWER, 4)]   # Cache
            ]
        },
        "level_1": {
            "commands": [
                "run      Run a command or script",
                "init     Create a new project",
                "add      Add dependencies to the project"
            ],
            "options": [
                "-n, --no-cache     Avoid reading from or writing to the cache",
                "--cache-dir <DIR>  Path to the cache directory"
            ]
        }
    }
    
    # Test level 0 headers
    level_0 = patterns.get(0, [])
    sections = [p.line.strip() for p in level_0 if p.line.strip().endswith(':')]
    assert sections == expected_output["level_0"]["sections"]
    
    # Test level 1 commands
    level_1 = patterns.get(1, [])
    commands = [p.line.strip() for p in level_1 if not p.line.strip().startswith('-')]
    assert commands == expected_output["level_1"]["commands"]
    
    # Test level 1 options
    options = [p.line.strip() for p in level_1 if p.line.strip().startswith('-')]
    assert options == expected_output["level_1"]["options"]

def test_cli_pattern_sequence(cli_docs):
    """Test exact character class sequences"""
    processor = GrammarProcessor()
    patterns = processor.analyze_patterns(cli_docs)
    
    # Test command pattern
    command_pattern = next(p for p in patterns[1] if "run" in p.line)
    expected_sequence = [
        (CharClass.ALPHA_LOWER, 3),      # run
        (CharClass.WHITESPACE, 6),       # spaces
        (CharClass.ALPHA_UPPER, 3),      # Run
        (CharClass.WHITESPACE, 1),       # space
        (CharClass.ALPHA_LOWER, 7)       # command
    ]
    assert command_pattern.horizontal == expected_sequence
    
    # Test option pattern
    option_pattern = next(p for p in patterns[1] if "--no-cache" in p.line)
    expected_sequence = [
        (CharClass.OPERATOR, 1),         # -
        (CharClass.ALPHA_LOWER, 1),      # n
        (CharClass.SEPARATOR, 1),        # ,
        (CharClass.WHITESPACE, 1),       # space
        (CharClass.OPERATOR, 2),         # --
        (CharClass.ALPHA_LOWER, 8)       # no-cache
    ]
    assert option_pattern.horizontal == expected_sequence

def test_cli_vertical_structure(cli_docs):
    """Test vertical pattern structure"""
    processor = GrammarProcessor()
    patterns = processor.analyze_patterns(cli_docs)
    
    expected_structure = {
        0: [(0, 1), (0, 1), (0, 1)],           # Headers
        1: [(1, 3), (1, 1), (1, 2)],           # Commands & Options
    }
    
    for level, expected_counts in expected_structure.items():
        level_patterns = patterns.get(level, [])
        counts = [p.vertical[0] for p in level_patterns if p.line.strip()]
        assert counts == expected_counts

def test_cli_blocks(cli_docs):
    """Test contiguous block detection"""
    processor = GrammarProcessor()
    blocks = processor.get_level_starts(1)  # Get level 1 blocks
    
    expected_blocks = [
        ("run      Run a command or script", 5),           # Commands block start
        ("-n, --no-cache     Avoid reading from", 10)      # Options block start
    ]
    
    assert [(line.strip(), num) for line, num in blocks] == expected_blocks

def test_academic_paper():
    """Test parsing of academic paper format"""
    test_input = """
Abstract
========
This is the abstract text.

1. Introduction
--------------
Background information...

1.1 Related Work
~~~~~~~~~~~~~~~
Previous studies show...
"""
    doc_processor = DocumentProcessor()
    patterns = doc_processor.process_document(test_input)
    
    # Verify structure
    assert patterns[0].pattern_type == 'heading'
    assert patterns[0].attributes['text'] == 'Abstract'
    assert patterns[1].pattern_type == 'paragraph'
    assert patterns[2].pattern_type == 'heading'
    assert patterns[2].attributes['text'] == '1. Introduction'

def test_legal_document():
    """Test parsing of legal document format"""
    test_input = """
TERMS AND CONDITIONS
-------------------

1. DEFINITIONS
   
   1.1 "Agreement" means...
   
   1.2 "Service" refers to...

2. SCOPE
   
   2.1 This agreement covers...
"""
    doc_processor = DocumentProcessor()
    patterns = doc_processor.process_document(test_input)
    
    # Verify structure
    assert patterns[0].pattern_type == 'heading'
    assert any(p.pattern_type == 'list' for p in patterns)
    assert sum(1 for p in patterns if p.pattern_type == 'heading') == 3

def test_technical_spec():
    """Test parsing of technical specification"""
    test_input = """
API Specification
================

Endpoints
--------
| Method | Path | Description |
|--------|------|-------------|
| GET    | /api | Root endpoint|

Request Parameters
----------------
* id: string (required)
* type: string (optional)
"""
    doc_processor = DocumentProcessor()
    patterns = doc_processor.process_document(test_input)
    
    # Verify structure
    table_pattern = next(p for p in patterns if p.pattern_type == 'table')
    assert table_pattern.attributes['columns'] == 3
    
    list_items = [p for p in patterns if p.pattern_type == 'list']
    assert len(list_items) == 2

def test_wiki_content():
    """Test parsing of wiki-style content"""
    test_input = """
= Main Title =
== Section 1 ==
Some text here...

=== Subsection ===
* Point 1
* Point 2
  * Nested point
  * Another nested point

== Section 2 ==
Code example:
    def example():
        return True
"""
    doc_processor = DocumentProcessor()
    patterns = doc_processor.process_document(test_input)
    
    # Verify structure
    assert patterns[0].pattern_type == 'heading'
    assert patterns[0].attributes['text'] == 'Main Title'
    assert patterns[1].pattern_type == 'heading'
    assert patterns[1].attributes['text'] == 'Section 1'
    assert patterns[2].pattern_type == 'paragraph'
    assert patterns[3].pattern_type == 'heading'
    assert patterns[3].attributes['text'] == 'Subsection'
    assert patterns[4].pattern_type == 'list'
    assert patterns[5].pattern_type == 'list'
    assert patterns[6].pattern_type == 'list'
    assert patterns[7].pattern_type == 'list'
    assert patterns[8].pattern_type == 'heading'
    assert patterns[8].attributes['text'] == 'Section 2'
    assert patterns[9].pattern_type == 'paragraph'
    assert patterns[10].pattern_type == 'code'
