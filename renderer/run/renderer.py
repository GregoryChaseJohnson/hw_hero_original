 # renderer.py

import pickle
import re
from block_creation import ReplacementBlock, DeleteBlock
from utils import apply_colors


def calculate_ride_along(block, leading_edge):
    if not block.ride_along_eligible:
        return False
    required_threshold = block.ride_along_end
    return leading_edge >= required_threshold


def insert_ride_along(block, leading_edge, annotated_line, tokens, original_sentence_str):
    """
    Insert ride-along text into the annotated line (green) and mark it as red in the final sentence tokens.
    """
    if not isinstance(block, ReplacementBlock):
        raise ValueError("Unsupported block type for ride-along")

    start = block.red_end + 1
    end = block.ride_along_end

    # Extract the ride-along text
    ride_along_text = original_sentence_str[start:end]

    # Remove leading spaces from ride-along text and adjust start index
    while ride_along_text and ride_along_text[0].isspace():
        ride_along_text = ride_along_text[1:]
        start += 1  # Adjust start index to match trimmed text

    # Ensure the annotated_line is long enough
    while len(annotated_line) < leading_edge:
        annotated_line.append({'char': ' ', 'type': 'equal'})

    # Add ride-along text to annotated_line (green for annotations above)
    for char in ride_along_text:
        annotated_line.append({'char': char, 'type': 'corrected'})

    # Mark the ride-along text as red (incorrect) in the final sentence tokens
    for i in range(start, start + len(ride_along_text)):
        tokens[i]['type'] = 'replace'

    # Update leading_edge
    leading_edge += len(ride_along_text)
    return leading_edge

def render_corrections(tokens, blocks):
    original_sentence_str = "".join(t['char'] for t in tokens)
    annotated_line = []
    leading_edge = 0

    for idx, block in enumerate(blocks):
        if hasattr(block, "processed") and block.processed:
            continue

        if isinstance(block, ReplacementBlock):
            corrected_text = block.replacement_text
            insertion_point = max(leading_edge, block.red_start)

            # Ensure annotated_line is long enough
            while len(annotated_line) < insertion_point:
                annotated_line.append({'char': ' ', 'type': 'equal'})

            # Insert corrected text as corrected tokens
            for char in corrected_text:
                annotated_line.append({'char': char, 'type': 'corrected'})

            # Update leading_edge
            leading_edge = insertion_point + len(corrected_text)

            # If needed, add a space after corrected text if not at sentence end
            if leading_edge < len(original_sentence_str):
                if original_sentence_str[leading_edge:leading_edge+1] not in ["\n"]:
                    annotated_line.append({'char': ' ', 'type': 'equal'})
                    leading_edge += 1

            # Check ride-along
            ride_along_required = calculate_ride_along(block, leading_edge)
            if ride_along_required:
                leading_edge = insert_ride_along(block, leading_edge, annotated_line, tokens, original_sentence_str)
                block.annotated_end = None  # Reset annotated_end if ride-along was inserted

        elif isinstance(block, DeleteBlock):
            # If you want pink tokens in the final sentence, mark them here
            tokens[block.delete_start]['type'] = 'delete'

    # Apply colors to annotated line
    annotated_line_colored = apply_colors(annotated_line)

    # Apply colors to final sentence tokens
    final_sentence_colored = apply_colors(tokens)

    return annotated_line, tokens

def save_renderer_output(annotated_lines, final_sentences, blocks_by_sentence):
    """
    Cache renderer outputs for post-processing.
    """
    with open("renderer_output.pkl", "wb") as f:
        pickle.dump({
            "annotated_lines": annotated_lines,
            "final_sentences": final_sentences,
            "blocks_by_sentence": blocks_by_sentence
        }, f)

def process_sentences(final_tokens_by_sentence, blocks_by_sentence):
    sentence_count = 1
    all_annotated_lines = []
    all_final_sentences = []
    all_blocks = []

    for tokens, blocks in zip(final_tokens_by_sentence, blocks_by_sentence):
        annotated_line, final_sentence = render_corrections(tokens, blocks)
        

        # Collect outputs
        all_annotated_lines.append(annotated_line)
        all_final_sentences.append(final_sentence)
        all_blocks.append(blocks)

        # Apply colors (for display purposes)
        annotated_line_colored = apply_colors(annotated_line)
        final_sentence_colored = apply_colors(final_sentence)

        # Print the full final outputs as before
        print(annotated_line_colored)
        print(final_sentence_colored)
        print()

        sentence_count += 1

    # Cache the outputs for post-processing
    save_renderer_output(all_annotated_lines, all_final_sentences, all_blocks)

    print("All sentences processed and cached.")
    return all_annotated_lines, all_final_sentences

if __name__ == "__main__":
    # If needed, we can place code here to run process_sentences
    # with a given data_loader or just leave it empty.
    pass