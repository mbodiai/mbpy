from enum import Enum, auto

class CharClass(Enum):
    # Structural 
    ENCLOSER_OPEN = auto()  # ({[<
    ENCLOSER_CLOSE = auto() # )}]>
    QUOTE = auto()          # "'`
    OPERATOR = auto()       # + - * / % = < > ! 
    SEPARATOR = auto()      # , ; :
    
    # Identifiers
    ALPHA_UPPER = auto()    # A-Z
    ALPHA_LOWER = auto()    # a-z
    NUMERIC = auto()        # 0-9
    UNDERSCORE = auto()     # _
    
    # Special
    PERIOD = auto()         # .
    HASH = auto()           # #
    BULLET = auto()         # - * •
    
    # Whitespace
    INDENT = auto()         # space/tab at start
    WHITESPACE = auto()     # other whitespace
    
    # Other
    SYMBOL = auto()         # Any other symbol
    UNKNOWN = auto()        # Unclassified

def get_char_class(char: str) -> CharClass:
    """Classify a single character into its CharClass"""
    if not char:
        return CharClass.UNKNOWN
        
    if char in '({[<':
        return CharClass.ENCLOSER_OPEN
    if char in ')}]>':
        return CharClass.ENCLOSER_CLOSE
    if char in '\'"`':
        return CharClass.QUOTE
    if char in '+-*/%=<>!':
        return CharClass.OPERATOR
    if char in ',:;':
        return CharClass.SEPARATOR
    if char.isupper():
        return CharClass.ALPHA_UPPER
    if char.islower():
        return CharClass.ALPHA_LOWER
    if char.isdigit():
        return CharClass.NUMERIC
    if char == '_':
        return CharClass.UNDERSCORE
    if char == '.':
        return CharClass.PERIOD
    if char == '#':
        return CharClass.HASH
    if char in '-*•●○◆■':
        return CharClass.BULLET
    if char.isspace():
        return CharClass.WHITESPACE
        
    return CharClass.SYMBOL
