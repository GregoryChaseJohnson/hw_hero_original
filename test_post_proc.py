import subprocess

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

def process_sentence(sentence: str):
    """
    Processes a single sentence by identifying red and green text sections.
    - Red text (uncorrected) is added to the original sentence with red color.
    - Green text (corrections) is placed in the 'above line' at the anchor position.
    """
    # Define ANSI color codes
    red_start = "\033[91m"
    green_start = "\033[92m"
    color_end = "\033[0m"

    # Flags for tracking color state
    in_red = False
    in_green = False

    # Trackers for sentence and corrections
    original_sentence = ""  # Builds the final original sentence with red text
    above_line = []         # Builds the line of corrections above the original sentence
    corrected_word = ""     # Holds the current correction (green text)
    anchor_pos = -1         # Position in original_sentence where correction should be placed
    index = 0               # Current index in the input sentence
    original_pos = 0        # Position in original_sentence

    # Loop through each character in the sentence
    while index < len(sentence):
        # Detect red section start
        if sentence.startswith(red_start, index):
            in_red = True
            in_green = False
            original_sentence += red_start  # Append red color code to original_sentence
            index += len(red_start)
            continue

        # Detect green section start
        elif sentence.startswith(green_start, index):
            in_green = True
            in_red = False
            index += len(green_start)
            continue

        # Detect end of color section
        elif sentence.startswith(color_end, index):
            # End red or green section and reset flags
            if in_red:
                original_sentence += color_end  # Close red color in original_sentence
            in_red = False
            in_green = False
            index += len(color_end)
            continue

        # Current character to process
        char = sentence[index]

        # Process red text (uncorrected text)
        if in_red:
            # Set the anchor position at the first red character
            if anchor_pos == -1:
                anchor_pos = original_pos
            original_sentence += char
            index += 1
            original_pos += 1

        # Process green text (corrected text)
        elif in_green:
            corrected_word += char
            index += 1

        # Process normal text
        else:
            # Place the corrected word in above_line at the anchor position
            if corrected_word and anchor_pos != -1:
                # Ensure above_line is long enough to hold the correction
                while len(above_line) < anchor_pos + len(corrected_word):
                    above_line.append(' ')
                # Insert corrected word at the anchor position in above_line
                for i, c in enumerate(corrected_word):
                    above_line[anchor_pos + i] = c
                corrected_word = ""  # Reset corrected word after placing
                anchor_pos = -1      # Reset anchor position

            # Append normal text character to the original sentence
            original_sentence += char
            index += 1
            original_pos += 1

    # Place any remaining corrected_word at the end of the sentence
    if corrected_word and anchor_pos != -1:
        # Ensure above_line is long enough to hold the correction
        while len(above_line) < anchor_pos + len(corrected_word):
            above_line.append(' ')
        # Insert any remaining corrected word at anchor_pos
        for i, c in enumerate(corrected_word):
            above_line[anchor_pos + i] = c

    # Build above_line_text with green color applied to corrected words
    above_line_text = ''
    i = 0
    while i < len(above_line):
        char = above_line[i]
        if char != ' ':
            # Start of a corrected word in green
            above_line_text += green_start
            while i < len(above_line) and above_line[i] != ' ':
                above_line_text += above_line[i]
                i += 1
            above_line_text += color_end
        else:
            # Space character
            above_line_text += ' '
            i += 1

    # Remove extra spaces from the end of above_line_text
    above_line_text = above_line_text.rstrip()
    original_line_text = original_sentence.strip()

    return above_line_text, original_line_text

def main():
    report_output = generate_report_from_script()

    if report_output:
        print("Successfully captured report output:")
        print(report_output)

        for line in report_output.splitlines():
            if line.strip():  # Ignore empty lines
                above_line, original_line = process_sentence(line)
                print(above_line)
                print(original_line)
                print("\n" + "-" * 40)

if __name__ == "__main__":
    main()
