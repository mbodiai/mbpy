import re
import json
from typing import List, Tuple, Dict, Any
from dataclasses import dataclass
from enum import Enum, IntEnum
from .grammar import GrammarProcessor, Node
from mbpy.helpers._display import to_click_options_args
from pathlib import Path
from typing import Optional, Literal
import rich_click as click
from rich.console import Console

class CharClass(IntEnum):
    WHITESPACE = 1
    ALPHA_UPPER = 2
    ALPHA_LOWER = 3
    NUMERIC = 4
    BULLET = 5
    OPERATOR = 6
    ENCLOSER_OPEN = 7
    ENCLOSER_CLOSE = 8
    SEPARATOR = 9
    QUOTE = 10  # Added 'QUOTE'
    HASH = 11    # Added 'HASH'
    PERIOD = 12  # Added 'PERIOD'

def classify_char(c: str) -> CharClass:
    if c.isspace():
        return CharClass.WHITESPACE
    if c.isupper():
        return CharClass.ALPHA_UPPER
    if c.islower():
        return CharClass.ALPHA_LOWER
    if c.isdigit():
        return CharClass.NUMERIC
    if c in '*-•':
        return CharClass.BULLET
    if c in '+-=/>':
        return CharClass.OPERATOR
    if c in '([{<':
        return CharClass.ENCLOSER_OPEN
    if c in ')]}>' :
        return CharClass.ENCLOSER_CLOSE
    if c in ',.;:':
        return CharClass.SEPARATOR
    return None

from .chars import get_char_class

@dataclass
class Classification:
    line: str
    line_number: int
    depth: int = 0
    outer_class: str = ""
    inner_group: int = 0
    sub_classifications: List['Classification'] = None

    def __post_init__(self):
        if self.sub_classifications is None:
            self.sub_classifications = []

@dataclass
class DocumentPattern:
    """Represents a generic document pattern"""
    content: str
    level: int
    pattern_type: str  # 'heading', 'paragraph', 'list', 'code', 'table', etc.
    attributes: Dict[str, Any]
    start_line: int
    end_line: int
    children: List['DocumentPattern'] = None
    
    def __post_init__(self):
        if self.children is None:
            self.children = []

class PatternMatcher:
    """Identifies common text patterns"""
    
    def __init__(self):
        self.pattern_rules = {
            'heading': self._is_heading,
            'list': self._is_list_item,
            'code': self._is_code_block,
            'table': self._is_table_row,
            'paragraph': self._is_paragraph_start
        }
    
    def _is_heading(self, line: str, prev_line: str = '', next_line: str = '') -> bool:
        # Headers can be:
        # 1. All caps
        # 2. Numbered (1.2.3)
        # 3. Markdown style (#, ##)
        # 4. Underlined by =, -, ~
        if not line.strip():
            return False
            
        if line.strip().isupper():
            return True
            
        if line.lstrip().startswith(('#', '*')):
            return True
            
        if next_line and set(next_line.strip()) <= {'-', '=', '~'}:
            return True
            
        # Check for numbered headers (1.2.3)
        if re.match(r'^\d+(\.\d+)*\s', line):
            return True
            
        return False
    
    def _is_list_item(self, line: str, prev_line: str = '', next_line: str = '') -> bool:
        # Match various list markers
        list_markers = [
            r'^\s*[-*+]\s',  # Unordered lists
            r'^\s*\d+[.)]\s',  # Numbered lists
            r'^\s*[a-zA-Z][.)]\s',  # Letter lists
            r'^\s*•\s',  # Bullet points
        ]
        return any(re.match(pattern, line) for pattern in list_markers)
    
    def _is_code_block(self, line: str, prev_line: str = '', next_line: str = '') -> bool:
        # Detect code blocks by indentation or markers
        if line.strip().startswith(('```', '~~~')):
            return True
            
        if prev_line.strip() and line.startswith('    '):
            return True
            
        return False
    
    def _is_table_row(self, line: str, prev_line: str = '', next_line: str = '') -> bool:
        # Detect table rows by requiring at least two '|' characters
        if not line.strip():
            return False
        # Check for markdown table separators with at least two '|'
        if '|' in line and line.count('|') >= 2:
            if set(line.strip()) <= {'-', '|', ':'}:
                return True
            return True
        return False
    
    def _is_paragraph_start(self, line: str, prev_line: str = '', next_line: str = '') -> bool:
        return bool(line.strip()) and not prev_line.strip()

class OutputFormat(Enum):
    MARKDOWN = "markdown"
    JSON = "json"


class DocumentProcessor:
    def __init__(self, max_depth: int = 5):
        self.max_depth = max_depth
        self._class_cache = {}
        self._indent_pattern = re.compile(r'^\s*')
        self.grammar_processor = GrammarProcessor()
        self.pattern_matcher = PatternMatcher()
        self.metadata = {}

    def _get_indent_level(self, line: str) -> int:
        if not line:
            return 0
        return len(self._indent_pattern.match(line).group())
    
    def classify_line(self, line: str) -> str:
        if not line.strip():
            return "blank"
        
        first_char = line.lstrip()[0]
        char_class = get_char_class(first_char)
        
        # Convert CharClass to line classification
        if char_class in (CharClass.ENCLOSER_OPEN, CharClass.ENCLOSER_CLOSE, CharClass.QUOTE):
            return "encloser"
        if char_class == CharClass.HASH:
            # Count consecutive hashes for header level
            hashes = len(re.match(r'^\s*(#+)', line).group(1))
            return "header" if hashes == 1 else f"subheader_{hashes}"
        if char_class == CharClass.PERIOD:
            return "documentation"
        if char_class == CharClass.BULLET:
            return "bullet"
        if char_class == CharClass.ALPHA_UPPER:
            return "capital_alpha"
        if char_class == CharClass.ALPHA_LOWER:
            return "lower_alpha"
        if char_class == CharClass.NUMERIC:
            return "numeric"
            
        return "other"

    def _process_chunk(self, 
                      lines: List[str], 
                      start: int, 
                      depth: int,
                      base_indent: int) -> Tuple[Classification, int]:
        if not lines or start >= len(lines) or depth > self.max_depth:
            return None, start
        
        current_line = lines[start]
        current_indent = self._get_indent_level(current_line)
        
        if current_indent < base_indent:
            return None, start
        
        if not current_line.strip():
            return None, start + 1
        
        classification = Classification(
            line=current_line,
            line_number=start + 1,
            depth=depth,
            outer_class=self.classify_line(current_line),
            inner_group=start + 1
        )
        
        pos = start + 1
        while pos < len(lines):
            next_line = lines[pos]
            next_indent = self._get_indent_level(next_line)
            
            if not next_line.strip():
                pos += 1
                continue
                
            if next_indent < current_indent:
                break
                
            if next_indent > current_indent:
                sub_class, new_pos = self._process_chunk(
                    lines, pos, depth + 1, next_indent
                )
                if sub_class:
                    classification.sub_classifications.append(sub_class)
                pos = new_pos
            else:
                break
        
        return classification, pos
    
    def process_document(self, text: str) -> List[DocumentPattern]:
        """Process document with enhanced pattern detection"""
        lines = text.splitlines()
        patterns = []
        current_pattern = None
        
        for i, line in enumerate(lines):
            prev_line = lines[i-1] if i > 0 else ''
            next_line = lines[i+1] if i < len(lines)-1 else ''
            
            indent = len(line) - len(line.lstrip())
            level = indent // 4
            
            # Detect pattern type
            pattern_type = None
            for ptype, checker in self.pattern_matcher.pattern_rules.items():
                if checker(line, prev_line, next_line):
                    pattern_type = ptype
                    break
            
            # If no pattern type is detected, classify based on content
            if not pattern_type:
                pattern_type = self._classify_based_on_content(line)
            
            if pattern_type:
                if current_pattern:
                    patterns.append(current_pattern)
                
                current_pattern = DocumentPattern(
                    content=line,
                    level=level,
                    pattern_type=pattern_type,
                    attributes=self._extract_attributes(line, pattern_type),
                    start_line=i + 1,
                    end_line=i + 1
                )
            else:
                current_pattern.content += '\n' + line
                current_pattern.end_line = i + 1
        
        if current_pattern:
            patterns.append(current_pattern)
        
        # Build hierarchy
        self._build_pattern_hierarchy(patterns)
        
        return patterns

    def _classify_based_on_content(self, line: str) -> str:
        """Classify line based on its content using flexible pattern matching rules"""
        if re.match(r'^\s*\w+\s*:\s*\w+\s*=\s*.+$', line):
            return 'variable'
        if re.match(r'^\s*#', line):
            return 'comment'
        if re.match(r'^\s*def\s+\w+\s*\(.*\)\s*:', line):
            return 'function'
        if re.match(r'^\s*class\s+\w+\s*\(.*\)\s*:', line):
            return 'class'
        return 'paragraph'

    def _extract_attributes(self, line: str, pattern_type: str) -> Dict[str, Any]:
        """Extract metadata attributes based on pattern type"""
        attrs = {}
        
        if pattern_type == 'heading':
            attrs['level'] = len(re.match(r'^#+', line).group()) if line.startswith('#') else 1
            attrs['text'] = line.lstrip('#').strip()
            
        elif pattern_type == 'list':
            attrs['marker_type'] = 'ordered' if re.match(r'^\s*\d+', line) else 'unordered'
            attrs['indent'] = len(line) - len(line.lstrip())
            
        elif pattern_type == 'code':
            if '```' in line:
                attrs['language'] = line.strip('`').strip()
                
        elif pattern_type == 'table':
            attrs['columns'] = len(re.findall(r'\|', line)) - 1 if '|' in line else len(line.split())
        
        elif pattern_type == 'variable':
            match = re.match(r'^\s*(\w+)\s*:\s*(\w+)\s*=\s*(.+)$', line)
            if match:
                attrs['name'] = match.group(1)
                attrs['type'] = match.group(2)
                attrs['value'] = match.group(3)
        
        elif pattern_type == 'function':
            match = re.match(r'^\s*def\s+(\w+)\s*\(.*\)\s*:', line)
            if match:
                attrs['name'] = match.group(1)
        
        elif pattern_type == 'class':
            match = re.match(r'^\s*class\s+(\w+)\s*\(.*\)\s*:', line)
            if match:
                attrs['name'] = match.group(1)
        
        return attrs

    def _get_node_class(self, node: Node) -> str:
        """Get the class type of a node based on its type and value"""
        if node.type == 'token':
            first_char = node.value[0] if node.value else ''
            return self.classify_line(first_char)
        return "other"

    def _build_pattern_hierarchy(self, patterns: List[DocumentPattern]) -> None:
        """Build parent-child relationships between patterns"""
        stack = []
        
        for pattern in patterns:
            while stack and stack[-1].level >= pattern.level:
                stack.pop()
                
            if stack:
                stack[-1].children.append(pattern)
                
            stack.append(pattern)
    
    def _convert_node_to_classifications(self, node: Node) -> List[Classification]:
        """Convert grammar nodes to classifications"""
        classifications = []
        def process_node(n: Node, depth: int = 0):
            classification = Classification(
                line=self._node_to_line(n),
                line_number=n.metadata.get('line', 0),
                depth=depth,
                outer_class=self._get_node_class(n),
                inner_group=n.metadata.get('line', 0)
            )
            if n.children:
                for child in n.children:
                    sub_class = process_node(child, depth + 1)
                    if sub_class:
                        classification.sub_classifications.append(sub_class)
            return classification
            
        if node.children:
            for child in node.children:
                result = process_node(child)
                if result:
                    classifications.append(result)
        return classifications
    
    def _process_document_fallback(self, text: str) -> List[Classification]:
        # Original line-based processing logic
        lines = text.splitlines()
        classifications = []
        pos = 0
        
        while pos < len(lines):
            classification, new_pos = self._process_chunk(
                lines, pos, 0, 0
            )
            if classification:
                classifications.append(classification)
            pos = new_pos if new_pos > pos else pos + 1
        
        return classifications
    
    def group_by_outer_class(self, classifications: List[Classification]) -> Dict[str, List[Classification]]:
        grouped = {}
        for c in classifications:
            grouped.setdefault(c.outer_class, []).append(c)
        return grouped
    
    def format_output(self, 
                     patterns: List[DocumentPattern],
                     format_type: OutputFormat = OutputFormat.MARKDOWN) -> str:
        if format_type == OutputFormat.JSON:
            return self._format_json(patterns)
        return self._format_markdown(patterns)
    
    def _format_json(self, patterns: List[DocumentPattern]) -> str:
        def pattern_to_dict(p):
            return {
                'type': p.pattern_type,
                'content': p.content,
                'level': p.level,
                'attributes': p.attributes,
                'lines': {'start': p.start_line, 'end': p.end_line},
                'children': [pattern_to_dict(child) for child in p.children]
            }
        # Return a single pattern dictionary instead of a list
        return json.dumps(pattern_to_dict(patterns[0]), indent=2)

    def _classifications_to_json(self, classifications: List[Classification]):
        def serialize_classification(c):
            return {
                "line": c.line,
                "line_number": c.line_number,
                "depth": c.depth,
                "outer_class": c.outer_class,
                "inner_group": c.inner_group,
                "sub_classifications": [
                    serialize_classification(sub) for sub in c.sub_classifications
                ],
            }
        return [serialize_classification(c) for c in classifications]

    def _format_markdown(self, classifications: List[Classification]) -> str:
        lines = []
        
        def _append_classification(c: Classification, depth: int = 0):
            indent = "    " * depth
            lines.extend([
                f"{indent}<details>",
                f'{indent}<summary>{c.line.strip()} (Line {c.line_number})</summary>\n',
                f"{indent}- **{c.line.strip()}**",
                f"{indent}  - Outer Class: `{c.outer_class}`",
                f"{indent}  - Inner Group: `{c.inner_group}`"
            ])
            
            if c.sub_classifications:
                lines.extend([
                    f"\n{indent}<details>",
                    f"{indent}<summary>Sub-Classifications</summary>\n"
                ])
                for sub in c.sub_classifications:
                    _append_classification(sub, depth + 1)
                lines.append(f"{indent}</details>")
            
            lines.extend([f"{indent}</details>\n"])
        
        for c in classifications:
            _append_classification(c)
        
        return "\n".join(lines)
    
    def _node_to_line(self, node: Node) -> str:
        return node.value if node.value else ""

        return node.value if node.value else ""


console = Console()

@to_click_options_args("source")
async def docparse_command(
    source: str,
    format: Literal["markdown", "json"] = "markdown",
    docs: bool = False,
    code: bool = False,
    stats: bool = False,
    max_depth: int = 5,
    is_file: bool = True,
) -> None:
    """Parse and analyze documentation structure.

    Args:
        source: Path to file or string content to analyze
        format: Output format (markdown or json)
        docs: Include documentation analysis
        code: Include code block analysis 
        stats: Show document statistics
        max_depth: Maximum depth for nested structures
        is_file: Whether source is a file path (default True)

    Example Usage:
        # Parse from file
        docparse path/to/file.py
        
        # Parse from string
        docparse "# My Header\nSome content" --is-file=false
        
        # Parse with JSON output and stats
        docparse input.py --format json --stats
    """
    processor = DocumentProcessor(max_depth=max_depth)
    
    try:
        text = ""
        if is_file:
            with open(source, 'r', encoding='utf-8') as f:
                text = f.read()
        else:
            text = source
            
        patterns = processor.process_document(text)
        
        # Filter patterns based on docs/code flags
        if docs or code:
            filtered_patterns = []
            for p in patterns:
                if docs and p.pattern_type in ('heading', 'paragraph', 'list'):
                    filtered_patterns.append(p)
                if code and p.pattern_type == 'code':
                    filtered_patterns.append(p)
            patterns = filtered_patterns
        
        if stats:
            # Add basic statistics
            total_patterns = len(patterns)
            pattern_types = {}
            for p in patterns:
                pattern_types[p.pattern_type] = pattern_types.get(p.pattern_type, 0) + 1
                
            console.print("\n[bold]Document Statistics:[/bold]")
            console.print(f"Total patterns: {total_patterns}")
            console.print("\nPattern types:")
            for ptype, count in pattern_types.items():
                console.print(f"- {ptype}: {count}")
                
        output = processor.format_output(
            patterns,
            format_type=OutputFormat.JSON if format == "json" else OutputFormat.MARKDOWN
        )
        
        console.print(output)
        
    except Exception as e:
        console.print(f"[red]Error processing document: {str(e)}[/red]")



