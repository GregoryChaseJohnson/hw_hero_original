class Tokenizer:
    def __init__(self, text):
        self.text = text
        self.tokens = []

    def tokenize(self):
        """
        Tokenizes the input text into blocks with associated colors (normal, red, green).
        """
        import re

        red_code = "\033[91m"
        green_code = "\033[92m"
        reset_code = "\033[0m"

        pattern = re.compile(r'(\033\[\d+m)')
        split_text = pattern.split(self.text)
        current_color = "normal"

        for segment in split_text:
            if segment == red_code:
                current_color = "red"
            elif segment == green_code:
                current_color = "green"
            elif segment == reset_code:
                current_color = "normal"
            else:
                for char in segment:
                    self.tokens.append({"char": char, "color": current_color})

        return self.tokens


class BlockCreator:
    def __init__(self, tokens):
        self.tokens = tokens
        self.blocks = []

    def create_blocks(self):
        """
        Categorizes tokens into blocks: replace, insert, delete, normal.
        """
        current_block = {"type": None, "tokens": []}

        for token in self.tokens:
            char, color = token["char"], token["color"]

            if color == "red" or color == "green":
                block_type = "replace" if color == "red" else "insert"
                if current_block["type"] not in ["replace", "insert"]:
                    if current_block["tokens"]:
                        self.blocks.append(current_block)
                    current_block = {"type": block_type, "tokens": []}
                current_block["tokens"].append(token)
            elif color == "normal":
                if current_block["type"] != "normal":
                    if current_block["tokens"]:
                        self.blocks.append(current_block)
                    current_block = {"type": "normal", "tokens": []}
                current_block["tokens"].append(token)

        # Append the last block
        if current_block["tokens"]:
            self.blocks.append(current_block)

        return self.blocks


class Renderer:
    def __init__(self, blocks, threshold=8):
        self.blocks = blocks
        self.above_line = []
        self.original_line = []
        self.threshold = threshold
        self.leading_edge = 0

    def process_blocks(self):
        """
        Processes blocks to align corrections above the original text.
        """
        for block in self.blocks:
            if block["type"] == "normal":
                self.original_line.extend(block["tokens"])
            elif block["type"] in ["replace", "insert"]:
                self.handle_correction_block(block)

    def handle_correction_block(self, block):
        """
        Processes a correction block and places corrections above the original text.
        """
        short_correction = "".join(t["char"] for t in block["tokens"] if t["color"] == "green")
        anchor_point = self.find_anchor(block)

        # Adjust anchor point based on the leading edge
        insertion_point = max(anchor_point, self.leading_edge)
        self.insert_into_above_line(insertion_point, short_correction)
        self.leading_edge = insertion_point + len(short_correction)

        # Append to original line
        if block["type"] == "replace":
            self.original_line.extend([t for t in block["tokens"] if t["color"] == "red"])

    def find_anchor(self, block):
        """
        Finds the anchor point for a block.
        """
        for i, token in enumerate(block["tokens"]):
            if token["color"] == "red":
                return i
        return 0

    def insert_into_above_line(self, pos, text):
        """
        Inserts text into the above line at a specified position.
        """
        while len(self.above_line) < pos:
            self.above_line.append(" ")

        for i, char in enumerate(text):
            if pos + i < len(self.above_line):
                self.above_line[pos + i] = char
            else:
                self.above_line.append(char)

    def render(self):
        """
        Renders the aligned above line and original line as strings.
        """
        above_line_text = "".join(self.above_line).rstrip()
        original_line_text = "".join(t["char"] for t in self.original_line)
        return above_line_text, original_line_text


def process_sentence(sentence):
    """
    Processes a sentence and returns the above line, original line, and original sentence.
    """
    tokenizer = Tokenizer(sentence)
    tokens = tokenizer.tokenize()

    block_creator = BlockCreator(tokens)
    blocks = block_creator.create_blocks()

    renderer = Renderer(blocks)
    renderer.process_blocks()

    above_line, original_line = renderer.render()
    return above_line, original_line, sentence


def main():
    """
    Main function to process sentences from a script and output corrections.
    """
    report_output = "Sentence 1: The\033[91mDuring the\033[0m day, I just spent my free time for\033[91mhaving \033[92mhaving\033[0m brunch at a branch at the cafe\033[91m café\033[92m café\033[0m and walking around the town."

    if report_output:
        for line in report_output.splitlines():
            if line.strip():
                above_line, original_line, original = process_sentence(line)
                print("Original Sentence:")
                print(original)
                print("\nAbove Line:")
                print(above_line)
                print("\nOriginal Line:")
                print(original_line)
                print("\n" + "-" * 40)


if __name__ == "__main__":
    main()
