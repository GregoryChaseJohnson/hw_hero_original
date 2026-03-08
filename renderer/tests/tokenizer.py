import re

class TextTokenizer:
    def __init__(self, text):
        """
        Initialize the tokenizer with the input text.
        """
        self.text = text  # Store the input text
        self.red_start = "\033[91m"  # Red for replaced (incorrect original)
        self.green_start = "\033[92m"  # Green for replaced (corrected text)
        self.blue_start = "\033[94m"  # Blue for insertions
        self.pink_start = "\033[95;1m"  # Bright magenta (pink) for deletions
        self.color_end = "\033[0m"  # Reset color
        self.tokens = []

    def parse_text(self):
            """
            Tokenizes the input text into characters with associated colors and assigns indices.
            Ensures blue tokens remain blue, and spaces between contiguous blocks inherit the block's color.
            """
            # Improved regex to split cleanly into ANSI codes, spaces, and tokens
            pattern = re.compile(r'(\033\[\d+;?\d*m|\s+|\w+|[^\w\s])')
            split_text = pattern.findall(self.text)


            current_color = 'normal'
            token_index = 0

            for token in split_text:
                if token == self.red_start:
                    current_color = 'red'
                elif token == self.green_start:
                    current_color = 'green'
                elif token == self.blue_start:
                    current_color = 'blue'
                elif token == self.pink_start:
                    current_color = 'pink'
                elif token == self.color_end:
                    current_color = 'normal'
                else:
                    # Process each character in the token
                    for char in token:
                        if char == ' ':
                            # Spaces are always normal initially
                            self.tokens.append({'index': token_index, 'char': char, 'color': 'normal'})
                        else:
                            # All other characters inherit the current color
                            self.tokens.append({'index': token_index, 'char': char, 'color': current_color})
                        token_index += 1

            # Post-processing loop to fix spaces between contiguous blocks
            for i in range(1, len(self.tokens) - 1):
                current_token = self.tokens[i]
                prev_token = self.tokens[i - 1]
                next_token = self.tokens[i + 1]

                # Check if the current token is a space and its neighbors have the same color
                if current_token['char'] == ' ' and prev_token['color'] == next_token['color'] and prev_token['color'] != 'normal':
                    # Inherit the color of the neighbors
                    current_token['color'] = prev_token['color']

            
            return self.tokens
