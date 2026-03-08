class ReplacementBlock:
    def __init__(self, red_start, red_end, red_text, replacement_text):
        self.type = 'replace'
        self.red_start = red_start
        self.red_end = red_end
        self.red_text = red_text
        self.replacement_text = replacement_text
        self.ride_along_end = None
        self.ride_along_eligible = False
        self.adjacent_to_next = False  # Will be set later if needed

class DeleteBlock:
    def __init__(self, delete_start):
        self.type = 'delete'
        self.delete_start = delete_start

def create_blocks(tokens):
    """
    Create blocks from tokenized text for a single sentence.
    This function:
    - Identifies red and green segments, and deletes green tokens after reading them, finalizing corrected text.
    - Identifies pink (delete) segments.
    - Returns a list of blocks describing replacements and deletions.

    The tokens are modified in-place by removing green tokens.
    """
    blocks = []
    i = 0

    while i < len(tokens):
        if tokens[i]['type'] == 'replace':
            red_start = i
            red_text = ""
            replacement_text = ""
            red_end = None

            # Collect replace-type text
            while i < len(tokens) and tokens[i]['type'] == 'replace':
                red_text += tokens[i]['char']
                red_end = i
                i += 1

            # If corrected tokens follow, collect them and remove after
            if i < len(tokens) and tokens[i]['type'] == 'corrected':
                corrected_start = i
                while i < len(tokens) and tokens[i]['type'] == 'corrected':
                    replacement_text += tokens[i]['char']
                    i += 1

                # Remove corrected segment to finalize corrected text
                del tokens[corrected_start:i]
                i = corrected_start  # Reset i after removal

            # Create a ReplacementBlock
            blocks.append(ReplacementBlock(red_start, red_end, red_text, replacement_text))

        # Look for a delete-type segment (previously 'pink')
        elif i < len(tokens) and tokens[i]['type'] == 'delete':
            delete_start = i
            # Skip all continuous delete-type tokens
            while i < len(tokens) and tokens[i]['type'] == 'delete':
                i += 1
            blocks.append(DeleteBlock(delete_start))

        else:
            i += 1

    # Adjust ride-along logic
    for j in range(len(blocks) - 1):
        current_block = blocks[j]
        next_block = blocks[j + 1]

        current_block_end = getattr(current_block, 'red_end', getattr(current_block, 'delete_start', None))
        next_block_start = getattr(next_block, 'red_start', None)

        if current_block_end is not None and next_block_start is not None:
            distance = next_block_start - current_block_end
            if 3 < distance <= 19:
                current_block.ride_along_eligible = True
                current_block.ride_along_end = next_block_start

    return blocks

def process_tokens_to_blocks(tokenized_output):
    """
    Given tokenized_output from diff_lib_test2.py (a list of token lists, one per sentence),
    process each sentence through create_blocks, resulting in final corrected tokens and blocks.

    Returns:
        final_tokens_by_sentence: The corrected tokens for each sentence after green removal.
        blocks_by_sentence: The blocks (ReplacementBlock, DeleteBlock) for each sentence.
    """
    final_tokens_by_sentence = []
    blocks_by_sentence = []

    for sentence_tokens in tokenized_output:
        # Make a copy if desired, or work directly since we want final_tokens_by_sentence updated
        # Direct modification is okay as we only do it here.
        blocks = create_blocks(sentence_tokens)

        # After create_blocks, sentence_tokens now reflects corrected text (green removed)
        final_tokens_by_sentence.append(sentence_tokens)
        blocks_by_sentence.append(blocks)

    return final_tokens_by_sentence, blocks_by_sentence

if __name__ == "__main__":
    # Standalone mode: load tokenized_output and produce blocks_output
    import pickle
    with open("tokenized_output.pkl", "rb") as f:
        tokenized_output = pickle.load(f)

    final_tokens_by_sentence, blocks_by_sentence = process_tokens_to_blocks(tokenized_output)

    with open("blocks_output.pkl", "wb") as f:
        pickle.dump({
            "final_tokens_by_sentence": final_tokens_by_sentence,
            "blocks_by_sentence": blocks_by_sentence
        }, f)

    print("Blocks successfully saved to blocks_output.pkl")
