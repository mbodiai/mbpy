from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Union, Tuple
import lark
from .chars import CharClass, get_char_class

# Grammar definition for parsing arbitrary text structures
GRAMMAR = r"""
    ?start: block
    
    block: statement*
    
    ?statement: assignment
              | type_def
              | dict_literal
              | list_literal
              | COMMENT
              | DOCSTRING
    
    assignment: name ":" type_expr "=" value
    
    type_expr: name                    // Simple type like "int" or "str"
             | name "[" type_expr "]"  // Generic type like List[int]
             | name "(" type_expr ")"  // Callable type
             | "None"                  // Special case for None type
    
    type_def: name "[" type_expr "]"
    
    dict_literal: "{" (pair ("," pair)*)? "}"
    pair: (string | name) ":" value
    
    list_literal: "[" (value ("," value)*)? "]"
    
    ?value: dict_literal
          | list_literal
          | string
          | number
          | "None"
          | name
          | value "[" value "]"  // Allow indexed access
    
    name: /[a-zA-Z_][a-zA-Z0-9_]*/
    string: ESCAPED_STRING
    number: /[0-9]+/
    
    COMMENT: /#[^\n]*/
    DOCSTRING: /\"\"\".*?\"\"\"/s
    
    %import common.ESCAPED_STRING
    %import common.WS
    %ignore WS
"""

@dataclass
class Node:
    type: str
    value: Any
    children: Optional[List['Node']] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class Pattern:
    """Track character class patterns horizontally and vertically"""
    horizontal: List[Tuple[CharClass, int]]  # (char_class, count)
    vertical: List[Tuple[int, int]]          # (indent_level, count)
    line: str
    line_number: int

class GrammarProcessor:
    def __init__(self):
        self.parser = lark.Lark(GRAMMAR, parser='lalr', propagate_positions=True)
        self._level_patterns: Dict[int, List[Pattern]] = {}
    
    def analyze_patterns(self, text: str) -> Dict[int, List[Pattern]]:
        """Analyze character class patterns at each level"""
        self._level_patterns.clear()
        lines = text.splitlines()
        
        for line_num, line in enumerate(lines, 1):
            indent = len(line) - len(line.lstrip())
            level = indent // 4  # Assuming 4-space indentation
            
            # Analyze horizontal patterns
            current_class = None
            count = 0
            horizontals = []
            
            for char in line.lstrip():
                char_class = get_char_class(char)
                if char_class != current_class:
                    if current_class:
                        horizontals.append((current_class, count))
                    current_class = char_class
                    count = 1
                else:
                    count += 1
            
            if current_class:
                horizontals.append((current_class, count))
            
            pattern = Pattern(
                horizontal=horizontals,
                vertical=[(level, 1)],
                line=line,
                line_number=line_num
            )
            
            self._level_patterns.setdefault(level, []).append(pattern)
        
        # Consolidate vertical counts
        for level, patterns in self._level_patterns.items():
            if len(patterns) > 1:
                current_count = 1
                for i in range(1, len(patterns)):
                    if self._is_similar_pattern(patterns[i-1], patterns[i]):
                        current_count += 1
                        patterns[i].vertical = [(level, current_count)]
                    else:
                        current_count = 1
        
        return self._level_patterns
    
    def _is_similar_pattern(self, p1: Pattern, p2: Pattern) -> bool:
        """Check if two patterns have similar character class sequences"""
        if len(p1.horizontal) != len(p2.horizontal):
            return False
            
        return all(
            h1[0] == h2[0] and abs(h1[1] - h2[1]) <= 2  # Allow small variations
            for h1, h2 in zip(p1.horizontal, p2.horizontal)
        )
    
    def get_level_starts(self, level: int) -> List[Tuple[str, int]]:
        """Get the first line of each contiguous block at given level"""
        if level not in self._level_patterns:
            return []
            
        results = []
        patterns = self._level_patterns[level]
        
        start_idx = 0
        for i in range(1, len(patterns)):
            if not self._is_similar_pattern(patterns[i-1], patterns[i]):
                results.append((
                    patterns[start_idx].line,
                    patterns[start_idx].line_number
                ))
                start_idx = i
                
        # Add final block
        if patterns:
            results.append((
                patterns[start_idx].line,
                patterns[start_idx].line_number
            ))
            
        return results

    def parse(self, text: str) -> Node:
        tree = self.parser.parse(text)
        return self._transform_tree(tree)
        
    def _transform_tree(self, tree: lark.Tree) -> Node:
        """Convert Lark tree to our Node structure"""
        if isinstance(tree, lark.Token):
            return Node(
                type='token',
                value=tree.value,
                metadata={'line': tree.line, 'column': tree.column}
            )
            
        children = [self._transform_tree(child) for child in tree.children]
        return Node(
            type=tree.data,
            value=None,
            children=children,
            metadata={'line': tree.meta.line, 'column': tree.meta.column}
        )

    def to_executable(self, node: Node) -> str:
        """Convert parsed structure to executable Python code"""
        # Implementation depends on specific needs
        pass
