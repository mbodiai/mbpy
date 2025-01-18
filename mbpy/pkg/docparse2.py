class CharClass:
    ALPHA_UPPER = 'alpha_upper'
    ALPHA_LOWER = 'alpha_lower'
    INDENT = 'indent'
    NUMERIC = 'numeric'
    PERIOD = 'period'
    BULLET = 'bullet'
    COLON = 'colon'
    SEMICOLON = 'semicolon'
    SYMBOL = 'symbol'
    ENCLOSER = 'encloser'  # New category for all enclosing symbols
    WHITESPACE = 'whitespace'

class Pattern:
    def __init__(self):
        self.horizontal_classes = []  # List of (char_class, count)
        self.vertical_classes = []    # List of (indent_level, count)
        
    def add_horizontal(self, char_class, count):
        self.horizontal_classes.append((char_class, count))
        
    def add_vertical(self, indent_level, count):
        self.vertical_classes.append((indent_level, count))

def get_char_class(char):
    if char.isupper():
        return CharClass.ALPHA_UPPER
    if char.islower():
        return CharClass.ALPHA_LOWER
    if char.isnumeric():
        return CharClass.NUMERIC
    if char.isspace():
        return CharClass.WHITESPACE if char != ' ' else CharClass.INDENT
    if char == '.':
        return CharClass.PERIOD
    if char == ':':
        return CharClass.COLON
    if char == ';':
        return CharClass.SEMICOLON
    if char in '-*•●○◆■':
        return CharClass.BULLET
    if char in '(){}[]<>""\'`':  # All enclosing symbols grouped together
        return CharClass.ENCLOSER
    if char in ',!?#$%&+=^_|~@':  # Removed enclosers from symbols
        return CharClass.SYMBOL
    return None

def analyze_line(line):
    pattern = Pattern()
    
    indent_level = len(line) - len(line.lstrip())
    if indent_level > 0:
        pattern.add_vertical(indent_level, 1)
    
    current_class = None
    count = 0
    symbol_count = 0  # Track consecutive symbols
    
    for char in line:
        char_class = get_char_class(char)
        
        # Handle symbols specially
        if char_class == CharClass.SYMBOL:
            if current_class == CharClass.SYMBOL:
                symbol_count += 1
            else:
                # Flush previous pattern
                if current_class and count > 0:
                    pattern.add_horizontal(current_class, count)
                current_class = CharClass.SYMBOL
                symbol_count = 1
                count = 0
            continue
            
        # Add accumulated symbols if any
        if symbol_count > 0:
            if symbol_count > 0:
                pattern.add_horizontal(CharClass.SYMBOL, symbol_count)
            symbol_count = 0
            
        if char_class != current_class:
            if current_class and count > 0:
                pattern.add_horizontal(current_class, count)
            current_class = char_class
            count = 1
        else:
            count += 1
            
    # Handle final patterns
    if symbol_count > 0:
        pattern.add_horizontal(CharClass.SYMBOL, symbol_count)
    elif current_class and count > 0:
        pattern.add_horizontal(current_class, count)
        
    return pattern

def analyze_document(lines):
    patterns = []
    vertical_counts = {}
    level_chain = {}  # Track parent-child relationships
    
    # First pass - collect patterns and build indent hierarchy
    for line in lines:
        pattern = analyze_line(line)
        patterns.append(pattern)
        
        indent_level = pattern.vertical_classes[0][0] if pattern.vertical_classes else 0
        if indent_level > 0:
            # Find parent level
            parent_level = 0
            for level in sorted(vertical_counts.keys()):
                if level < indent_level:
                    parent_level = level
            level_chain[indent_level] = parent_level
            
            # Update counts
            vertical_counts[indent_level] = vertical_counts.get(indent_level, 0) + 1
        else:
            pattern.add_vertical(0, 1)  # Ensure root level is added
    
    # Second pass - rebuild vertical classes with proper hierarchy
    for pattern in patterns:
        current_level = pattern.vertical_classes[0][0] if pattern.vertical_classes else 0
        if current_level == 0:
            pattern.vertical_classes = [(0, 1)]  # Add root level
        else:
            # Build chain from root to current level
            chain = []
            level = current_level
            while level > 0:
                chain.append(level)
                level = level_chain.get(level, 0)
                
            # Rebuild vertical classes in correct order
            pattern.vertical_classes = []
            if chain:  # Only add levels if we have indentation
                pattern.add_vertical(0, 1)  # Root level
                for level in reversed(chain):
                    pattern.add_vertical(level, vertical_counts.get(level, 1))
    
    return patterns
