import sys
import re 
import json

sys.path.append('/home/keithuncouth/red_pen_app/renderer/tests')  # Adjust path to your `renderer` directory

from tokenizer import TextTokenizer
from block_creation import create_blocks
from script_runner import generate_report_from_script

ANSI_COLORS = {
    'normal': '\033[0m',
    'red': '\033[31m',
    'green': '\033[92m',
    'blue': '\033[34m',
    'pink': '\033[35m',
}

def strip_ansi(text):
    ansi_escape = re.compile(r'\033\[[0-9;]*m')
    return ansi_escape.sub('', text)

def calculate_ride_along(block, leading_edge):
    """
    Determine if ride-along text should be inserted for a block.

    Parameters:
    - block (dict): The block being processed.
    - leading_edge (int): Current position after corrected text and space.

    Returns:
    - bool: True if ride-along should occur, False otherwise.
    """
    # Check if ride-along is eligible
    if not block.get("ride_along_eligible", False):  # Defaults to False if key missing
        return False

    # Check if "ride_along_end" is present and valid
    required_threshold = block.get("ride_along_end")
    if required_threshold is None:
        return False  # If missing, ride-along cannot occur

    # Compare leading edge to required threshold
    return leading_edge >= required_threshold

def insert_ride_along(block, leading_edge, annotated_line, final_sentence):
    """
    Insert ride-along text into the annotated line.

    Parameters:
    - block (dict): Current block being processed.
    - leading_edge (int): Current position after inserting corrected text and space.
    - annotated_line (list): Line being annotated with corrections.
    - final_sentence (str): The complete sentence for reference.

    Returns:
    - int: Updated leading_edge after inserting ride-along text.
    """
    # Define start and end based on block type
    if block["type"] == "replace":
        start = block.get("red_end", 0) + 1  # Default to 0 if "red_end" is missing
    elif block["type"] == "insert":
        start = block.get("anchor", 0)  # Default to 0 if "anchor" is missing
    else:
        raise ValueError(f"Unsupported block type: {block.get('type')}")

    # Ride-along end is always defined in block metadata
    end = block.get("ride_along_end")
    if end is None:  # Check for missing or invalid "ride_along_end"
        raise ValueError("Ride-along end is missing in block metadata.")

    # Extract ride-along
    cleaned_sentence = strip_ansi(final_sentence)
    if start >= len(cleaned_sentence) or end > len(cleaned_sentence):
        raise IndexError("Start or end indices for ride-along text are out of bounds.")
    ride_along_text = cleaned_sentence[start:end]

    # Debug: Show the extracted ride-along text
    print(f"DEBUG: Ride-Along Text for Block: '{ride_along_text}' (Start: {start}, End: {end})")

    # Append ride-along text to annotated_line
    while len(annotated_line) < leading_edge:
        annotated_line.append(" ")  # Ensure alignment
    for char in ride_along_text:
        annotated_line.append(f"{ANSI_COLORS['green']}{char}\033[0m")

    # Return the updated leading_edge
    return end

def find_last_pink_anchor(blocks):
    """
    Find the anchor point of the last pink block in the block list.

    Parameters:
    - blocks (list): List of all blocks, where each block is a dictionary.

    Returns:
    - int or None: The anchor point of the last pink block, or None if no pink block exists.
    """
    for block in reversed(blocks):
        if block.get("type") == "pink":  # Check block type safely
            return block.get("anchor")  # Return anchor point if it exists
    return None

def is_orphaned_insert(block, idx, blocks):
    """
    Check if an insert block is orphaned (occurs after a SentenceEndBlock).

    Parameters:
    - block (dict): The block being checked.
    - idx (int): Index of the current block in the block list.
    - blocks (list): List of all blocks (dictionaries).

    Returns:
    - bool: True if the block is an orphaned insert block, False otherwise.
    """
    return (
        block.get("type") == "insert" and 
        idx > 0 and 
        blocks[idx - 1].get("type") == "sentence_end"
    )

def render_corrections(final_sentence, blocks):
    """
    Render the corrected text above the original sentence using metadata from blocks.
    """
    # Annotated line starts empty and grows according to block metadata
    annotated_line = []

    # Track the leading edge for placement
    leading_edge = 0

    for idx, block in enumerate(blocks):
        # Guard clause to skip processed blocks
        if block.get("processed", False):
            continue

        # Step 1: Calculate the modified anchor point for insert blocks
        if block["type"] == "insert":
            corrected_text = block["correct_text"]
            color = ANSI_COLORS["green"]

            # Check if the insert block is orphaned
            if is_orphaned_insert(block, idx, blocks):
                # Use last pink anchor point if available
                last_pink_anchor = find_last_pink_anchor(blocks)
                if last_pink_anchor is not None:
                    block["anchor"] = last_pink_anchor  # Update anchor point for clarity
                insertion_point = max(leading_edge, block["anchor"])
                block["processed"] = True
            else:
                # Standard insert logic
                modified_anchor_point = block["anchor"] - 1  # Shift one position left
                insertion_point = max(leading_edge, modified_anchor_point)
        elif block["type"] == "replace":
            corrected_text = block["correct_text"]
            color = ANSI_COLORS["green"]
            insertion_point = max(leading_edge, block["anchor"])
        else:
            continue  # Skip unsupported block types

        # DEBUG: Check block handling
        print(f"DEBUG: Block {idx}: Type={block['type']}, Anchor={block['anchor']}, "
              f"Insertion Point={insertion_point}, Leading Edge={leading_edge}")

        # Step 3: Ensure enough space in the annotated line
        while len(annotated_line) < insertion_point:
            annotated_line.append(" ")

        # Step 4: Add corrected text
        for char in corrected_text:
            annotated_line.append(f"{color}{char}\033[0m")

        # Step 5: Update leading edge
        leading_edge = insertion_point + len(corrected_text)
        if leading_edge < len(final_sentence):
            annotated_line.append(" ")
            leading_edge += 1

        # Step 6: Debug print for ride-along
        ride_along_required = calculate_ride_along(block, leading_edge)
        print(
            f"DEBUG: Block {idx}: Type={block['type']}, Anchor={block['anchor']}, "
            f"Insertion Point={insertion_point}, Leading Edge={leading_edge}, "
            f"Ride-Along Required={'Yes' if ride_along_required else 'No'}"
        )

        # Step 7: Insert ride-along text if required
        if ride_along_required:
            # Gather the ride-along text based on block type
            if block["type"] == "replace":
                start = block["red_end"]
            elif block["type"] == "insert":
                start = block["anchor"]
            else:
                print(f"DEBUG: Skipping ride-along for unsupported block type {block['type']}.")
                continue

            end = block["ride_along_end"]

            # Extract ride-along text and handle insertion
            ride_along_text = final_sentence[start:end]
            leading_edge = insert_ride_along(
                block, leading_edge, annotated_line, final_sentence
            )

    return "".join(annotated_line)

def test_renderer(input_file):
    """
    Test rendering logic by integrating block creation and formatting output.
    Process multiple tokenized sentences and blocks from a JSON file.
    """
    # Step 1: Load JSON file
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    annotated_outputs = []  # To store the annotated sentences for separate printing

    # Step 2: Iterate through each tokenized sentence and its blocks
    for item in data:
        tokenized_text = item["tokenized_text"]
        blocks = item["blocks"]

        # Construct the final sentence
        final_sentence = ''.join(
            f"{ANSI_COLORS.get(token['color'], '')}{token['char']}" for token in tokenized_text
        )
        final_sentence += '\033[0m'  # Reset color

        # Render the corrections above the final sentence
        annotated_line = render_corrections(final_sentence, blocks)

        # Original debug-style output
        print("\nAnnotated Line:")
        print(annotated_line)  # Annotated line (above)
        print("\nFinal Sentence:")
        print(final_sentence)  # Final sentence (below)
        print("\n" + "=" * 50 + "\n")  # Separator for readability

        # Collect annotated and original sentences for later
        annotated_outputs.append((annotated_line, final_sentence))

    # Print all annotated sentences in a realistic format, one by one
    print("\nRealistic Annotation View:")
    for annotated_line, final_sentence in annotated_outputs:
        print(f"{annotated_line}\n{final_sentence}\n")  # Print annotated and original line together

if __name__ == "__main__":
    # Replace 'processed_data.json' with your JSON file containing tokenized text and blocks
    test_renderer(input_file="processed_data.json")
