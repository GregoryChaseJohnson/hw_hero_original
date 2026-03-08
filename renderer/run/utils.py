# utils.py

ANSI_COLORS = {
    'equal': '\033[0m',      # normal
    'replace': '\033[91m',   # red
    'corrected': '\033[92m', # green
    'insert': '\033[92m',    # green
    'delete': '\033[91m',  # red
}

def apply_colors(tokens):
    """
    Convert a list of tokens with 'type' and 'char' fields into a colorized string.
    Each character is wrapped in the appropriate ANSI color code based on 'type'.
    Defaults to 'equal' if type is missing.
    """
    colored_output = []
    for token in tokens:
        c = token['char']
        typ = token.get('type', 'equal')
        color_code = ANSI_COLORS.get(typ, ANSI_COLORS['equal'])
        # Reset to normal after each character to ensure proper coloring
        colored_output.append(f"{color_code}{c}{ANSI_COLORS['equal']}")
    return "".join(colored_output)
