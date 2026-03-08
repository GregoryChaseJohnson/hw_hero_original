# align_overhang.py

import pickle
from utils import apply_colors

class Block:
    """
    Represents a red block and its associated replacementtext.
    """
    def __init__(self, block_id, red_start, red_end, replacement_text=None):
        self.block_id = block_id  # Numerical identifier
        self.red_start = red_start
        self.red_end = red_end
        self.replacement_text = replacement_text if replacement_text else []

    def compute_overhang(self):
        """
        Calculate overhang as (len(replacement_text) - block_length).
        """
        block_length = self.red_end - self.red_start + 1
        # Overhang is based on how many tokens exceed the block_length
        return max(len(self.replacement_text) - block_length, 0)

    def __str__(self):
        repl_str = "".join([t['char'] for t in self.replacement_text]) if self.replacement_text else "None"
        return f"Block(id={self.block_id}, red_start={self.red_start}, red_end={self.red_end}, replacement_text='{repl_str}')"


def identify_red_blocks(final_sentence):
    """
    Identify red blocks allowing a single space inside the block.
    Red tokens define a block. A single space is allowed within a block.
    More than one consecutive space or a non-red, non-space token ends the block.
    """
    def is_red(token):
        return token.get('type', 'equal') == 'replace'
    def is_space_char(token):
        return token['char'].isspace()

    def add_block(blocks, start, end):
        if start is not None and end is not None and end >= start:
            blocks.append({'block_start': start, 'block_end': end})

    blocks = []
    block_start = None
    space_count = 0

    for idx, token in enumerate(final_sentence):
        if is_red(token):
            if block_start is None:
                block_start = idx
            space_count = 0
        elif is_space_char(token):
            space_count += 1
            if space_count > 1:
                # More than one consecutive space ends the block
                add_block(blocks, block_start, idx - space_count)
                block_start = None
                space_count = 0
        else:
            # Non-red, non-space ends the block
            add_block(blocks, block_start, idx - 1 - space_count)
            block_start = None
            space_count = 0

    # Close any remaining block
    add_block(blocks, block_start, len(final_sentence) - 1 - space_count)

    return blocks

def get_green_search_area(red_blocks, current_block_index, annotated_line_length):
    """
    Determine the search area for a given red
     block.
    """
    search_start = red_blocks[current_block_index]['block_start']
    if current_block_index + 1 < len(red_blocks):
        search_end = red_blocks[current_block_index + 1]['block_start']
    else:
        search_end = annotated_line_length
    if search_end < search_start:
        search_end = search_start
    return search_start, search_end

def extract_replacement_text(annotated_line, red_blocks, block_index):
    search_start, search_end = get_green_search_area(red_blocks, block_index, len(annotated_line))
    segment = annotated_line[search_start:search_end]

    collected = []
    consecutive_spaces = 0

    for token in segment:
        col = token.get('type', 'equal')
        ch = token['char']

        if col == 'corrected':
            consecutive_spaces = 0
            collected.append(token)
        elif col == 'equal' and ch.isspace():
            if collected:
                consecutive_spaces += 1
                if consecutive_spaces == 1:
                    collected.append(token)
                else:
                    # Two consecutive spaces -> stop collecting
                    collected = collected[:-1]
                    break
            # else ignore spaces before any replacement token
        else:
            # Any other token breaks the sequence
            break

    # Trim trailing spaces at the end of collected tokens if any
    while collected and collected[-1]['char'].isspace():
        collected.pop()

    return collected

def define_blocks(annotated_line, final_sentence):
    """
    Define red blocks and associate replacement text.
    """
    red_blocks = identify_red_blocks(final_sentence)
    blocks = []

    for i, rb in enumerate(red_blocks):
        replacement_text = extract_replacement_text(annotated_line, red_blocks, i)
        blocks.append(Block(i, rb['block_start'], rb['block_end'], replacement_text))

    return blocks
def insert_spaces(final_sentence, blocks):
    """
    Insert spaces into the final sentence based on overhang,
    and adjust subsequent blocks' positions accordingly.
    """
    for i, block in enumerate(blocks):
        overhang = block.compute_overhang()
        if overhang > 0:
            # Find the first space after the block
            insertion_point = block.red_end + 1
            while insertion_point < len(final_sentence) and not final_sentence[insertion_point]['char'].isspace():
                insertion_point += 1

            # Insert spaces if a valid space is found
            if insertion_point < len(final_sentence) and final_sentence[insertion_point]['char'].isspace():
                spaces = [{'char': ' ', 'type': 'equal'}] * overhang
                final_sentence = final_sentence[:insertion_point + 1] + spaces + final_sentence[insertion_point + 1:]

                # Shift subsequent blocks
                for j in range(i + 1, len(blocks)):
                    blocks[j].red_start += overhang
                    blocks[j].red_end += overhang

    return final_sentence

def place_replacement_text(blocks, final_sentence):
    """
    Place replacement text on the annotated line, dynamically extending it as needed.
    Add a period to the replacement text if it logically ends the sentence.
    """
    annotated_line = []
    max_replaced_idx = -1

    # Step 1: Place all replacement text and track the farthest extent
    for block in blocks:
        replacement_length = len(block.replacement_text)
        original_length = block.red_end - block.red_start + 1

        # Ensure annotated_line is long enough before placement
        required_length = block.red_start + replacement_length
        if len(annotated_line) < required_length:
            annotated_line.extend([{'char': ' ', 'type': 'equal'}] * (required_length - len(annotated_line)))

        # Place the replacement text
        for idx, token in enumerate(block.replacement_text):
            target_idx = block.red_start + idx
            annotated_line[target_idx] = token
            # Track the farthest replaced character
            max_replaced_idx = max(max_replaced_idx, target_idx)

    # Step 2: Determine the last meaningful position in the final sentence
    last_meaningful_idx = len(final_sentence) - 1
    while last_meaningful_idx >= 0 and final_sentence[last_meaningful_idx]['char'].isspace():
        last_meaningful_idx -= 1

    # Step 3: Check if the replaced text logically ends the sentence
    if max_replaced_idx >= last_meaningful_idx:
        # Find the last non-space character in the annotated line
        last_non_space_idx = max_replaced_idx
        while last_non_space_idx >= 0 and annotated_line[last_non_space_idx]['char'].isspace():
            last_non_space_idx -= 1

        # Add a period if the replacement text ends the sentence
        if last_non_space_idx >= 0:
            last_char = annotated_line[last_non_space_idx]['char']
            if last_char in ['"', '”', '“', '‘', '’', "'"]:
                # Insert period before the quote
                annotated_line.insert(last_non_space_idx, {'char': '.', 'type': 'equal'})
            else:
                # Append period at the end or insert after replacement text
                if last_non_space_idx == len(annotated_line) - 1:
                    annotated_line.append({'char': '.', 'type': 'corrected'})
                else:
                    insert_idx = last_non_space_idx + 1
                    while insert_idx < len(annotated_line) and annotated_line[insert_idx]['char'].isspace():
                        insert_idx += 1
                    annotated_line.insert(insert_idx, {'char': '.', 'type': 'equal'})

    return annotated_line

def finalize_transformation(annotated_lines, final_sentences):
    """
    Perform the final transformation for each sentence.
    """
    for i, (annotated_line, final_sentence) in enumerate(zip(annotated_lines, final_sentences)):

        # Define blocks and associate replacement text
        blocks = define_blocks(annotated_line, final_sentence)

        # Insert spaces based on overhang
        final_sentence = insert_spaces(final_sentence, blocks)

        # Place replacement text after adjusting positions
        annotated_line = place_replacement_text(blocks, final_sentence)

        # Print results
        print("\nFinal Annotated Line (Colored):")
        print(apply_colors(annotated_line))
        print(apply_colors(final_sentence))

        annotated_lines[i] = annotated_line
        final_sentences[i] = final_sentence

    return annotated_lines, final_sentences

if __name__ == "__main__":
    # 1. Load data
    with open("annotated_line_space_cleanup_output.pkl", "rb") as f:
        data = pickle.load(f)
        annotated_lines = data["annotated_lines"]
        final_sentences = data["final_sentences"]

    # 3. Run the finalize transformation, which also prints colorized output
    updated_annotated_lines, updated_final_sentences = finalize_transformation(
        annotated_lines, final_sentences
    )

    # 4. (Optionally) save the updated data
    with open("final_output.pkl", "wb") as f:
        pickle.dump({
            "annotated_lines": updated_annotated_lines,
            "final_sentences": updated_final_sentences
        }, f)
    print("\nFinal processed data saved to final_output.pkl")