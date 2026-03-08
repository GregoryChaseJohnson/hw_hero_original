import subprocess
import re

def generate_report_from_script():
    """
    Calls the existing script to generate the report output, returning the output string.
    """
    try:
        result = subprocess.run(
            ["python3", "sentence_parse.py"], capture_output=True, text=True, check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print("Error running existing_script.py:", e)
        return ""

class TextCorrector:
    def __init__(self, text, threshold=5):
        self.text = text
        self.red_start = "\033[91m"
        self.green_start = "\033[92m"
        self.color_end = "\033[0m"
        self.tokens = []
        self.above_line = []
        self.original_line = []
        self.leading_edge = 0  # Tracks the furthest position written in the above line
        self.previous_correction_end = None  # Tracks the last correction's end position
        self.threshold = threshold  # Threshold for orphaned text handling

    def parse_text(self):
        """
        Parses the input text into a list of tokens, each with a character and its color.
        """
        pattern = re.compile('(\033\[\d+m)')
        split_text = pattern.split(self.text)
        color = 'normal'
        for segment in split_text:
            if segment == self.red_start:
                color = 'red'
            elif segment == self.green_start:
                color = 'green'
            elif segment == self.color_end:
                color = 'normal'
            else:
                for char in segment:
                    self.tokens.append({'char': char, 'color': color})

    def adjust_anchor_point(self, anchor_point):
        """
        Adjusts the anchor point to avoid conflicts with the leading edge of the text above.
        Always ensures corrections align sequentially without overwriting.
        """
        if anchor_point <= self.leading_edge:
            anchor_point = self.leading_edge + 1  # Move to the next available position
        return anchor_point

    def check_and_handle_orphaned_text(self, current_anchor):
        """
        Checks if there is orphaned text between corrections and moves it to the above line.
        """
        if self.previous_correction_end is not None:
            # Calculate distance from previous correction to the current anchor
            distance = current_anchor - self.previous_correction_end
            print(f"Current Anchor: {current_anchor}, Previous End: {self.previous_correction_end}, Distance: {distance}")
            print(f"Leading Edge: {self.leading_edge}, Threshold: {self.threshold}")

            if distance > 0:  # There’s a gap between corrections
                start = self.previous_correction_end
                end = current_anchor

                for idx in range(start, end):
                    if idx < len(self.original_line):
                        token = self.original_line[idx]
                        if token['color'] == 'normal':
                            char = token['char']
                            print(f"Detected Orphaned Text: {char} at {idx}")
                            # Move orphaned text to the above line
                            while len(self.above_line) <= self.leading_edge:
                                self.above_line.append({'char': ' ', 'color': 'normal'})
                            self.above_line[self.leading_edge] = {'char': char, 'color': 'normal'}
                            self.leading_edge += 1  # Update leading edge

    def insert_into_above_line(self, pos, text):
        """
        Inserts corrected text into the above line at the specified position.
        Adjusts position dynamically to avoid overlaps.
        """
        # Ensure sufficient space in the above line
        while len(self.above_line) < pos:
            self.above_line.append({'char': ' ', 'color': 'normal'})

        # Insert text and update leading edge
        for i, char in enumerate(text):
            if pos + i < len(self.above_line):
                self.above_line[pos + i] = {'char': char, 'color': 'green'}
            else:
                self.above_line.append({'char': char, 'color': 'green'})
        self.leading_edge = max(self.leading_edge, pos + len(text))

        return pos, pos + len(text)

    def process_corrections(self):
        """
        Processes the tokens to separate corrections and align them above the original sentence.
        """
        index = 0
        in_red = False
        in_green = False
        anchor_pos = -1
        corrected_word = ''
        original_pos = 0  # Position in original_line
        prev_color = 'normal'

        while index < len(self.tokens):
            token = self.tokens[index]
            color = token['color']
            char = token['char']
            if color == 'red':
                if not in_red:
                    in_red = True
                    in_green = False
                    anchor_pos = original_pos  # Set anchor position at the start of red text
                self.original_line.append(token)
                index += 1
                original_pos += 1
            elif color == 'green':
                if not in_green:
                    in_green = True
                    in_red = False
                    correction_type = 'replacement' if prev_color == 'red' else 'insertion'

                corrected_word += char
                index += 1
            else:
                # Handle normal text
                if in_green:
                    if corrected_word and anchor_pos != -1:
                        # Adjust anchor point for conflicts
                        anchor_pos = self.adjust_anchor_point(anchor_pos)
                        
                        # Handle orphaned text if necessary
                        if self.leading_edge > anchor_pos - self.threshold:
                            self.check_and_handle_orphaned_text(anchor_pos)
                        
                        # Insert correction
                        correction_start, correction_end = self.insert_into_above_line(anchor_pos, corrected_word)
                        self.previous_correction_end = correction_end
                        corrected_word = ''
                        anchor_pos = -1
                    in_green = False
                if in_red:
                    in_red = False
                    anchor_pos = -1
                self.original_line.append(token)
                index += 1
                original_pos += 1
            prev_color = color

        # Handle leftover corrected word
        if corrected_word and anchor_pos != -1:
            anchor_pos = self.adjust_anchor_point(anchor_pos)
            self.check_and_handle_orphaned_text(anchor_pos)
            correction_start, correction_end = self.insert_into_above_line(anchor_pos, corrected_word)

    def get_above_line_text(self):
        """
        Builds the above line text with ANSI color codes applied.
        """
        text = ''
        prev_color = 'normal'
        for token in self.above_line:
            color = token['color']
            char = token['char']
            if color != prev_color:
                if prev_color != 'normal':
                    text += self.color_end
                if color == 'green':
                    text += self.green_start
            text += char
            prev_color = color
        if prev_color != 'normal':
            text += self.color_end
        return text.rstrip()

    def get_original_sentence_text(self):
        """
        Builds the original sentence text with ANSI color codes applied to red text.
        """
        text = ''
        prev_color = 'normal'
        for token in self.original_line:
            color = token['color']
            char = token['char']
            if color != prev_color:
                if prev_color != 'normal':
                    text += self.color_end
                if color == 'red':
                    text += self.red_start
            text += char
            prev_color = color
        if prev_color != 'normal':
            text += self.color_end
        return text.strip()

def process_sentence(sentence: str):
    """
    Processes a single sentence to separate corrections and align them above the original text.
    """
    corrector = TextCorrector(sentence)
    corrector.parse_text()
    corrector.process_corrections()
    above_line = corrector.get_above_line_text()
    original_line = corrector.get_original_sentence_text()
    return above_line, original_line, sentence  # Return the original sentence as well

def main():
    report_output = generate_report_from_script()

    if report_output:
        for line in report_output.splitlines():
            if line.strip():  # Ignore empty lines
                above_line, original_line, original = process_sentence(line)
                # Print the original sentence with colors intact
                print("Original Sentence:")
                print(original)
                # Print the aligned above line and processed original line
                print(f"\n{above_line}")
                print(f"{original_line}")
                print("\n" + "-" * 40)


if __name__ == "__main__":
    main()
