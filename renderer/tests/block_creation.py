class ReplacementBlock:
    def __init__(self, anchor_point, red_end, red_text, replacement_text):
        self.type = 'replace'
        self.anchor_point = anchor_point
        self.red_end = red_end
        self.red_text = red_text
        self.replacement_text = replacement_text  # Short correction
        self.ride_along_end = None 
        self.ride_along_eligible = False 
        self.actual_start = None  # Added for tracking
        self.actual_end = None    # Added for tracking
       

class InsertionBlock:
    def __init__(self, anchor_point, insert_text):
        self.type = 'insert'
        self.anchor_point = anchor_point
        self.insert_text = insert_text  # Short correction
        self.ride_along_end = None 
        self.ride_along_eligible = False 
        self.actual_start = None  # Added for tracking
        self.actual_end = None    # Added for tracking

class PinkBlock:
    def __init__(self, anchor_point):
        self.type = 'pink'
        self.anchor_point = anchor_point

class SentenceEndBlock:
    def __init__(self, anchor_point):
        self.type = 'sentence_end'
        self.anchor_point = anchor_point


SENTENCE_END_PUNCTUATION = ['.', '!', '?', '...', '"', "'"]

def is_sentence_end(tokens, index):
    """Check if the current token marks the end of a sentence."""
    # Ensure there's room for a punctuation and newline
    if index + 2 >= len(tokens):
        return False
    
    # Check if the next two tokens form a sentence-ending sequence
    return (
        tokens[index + 1]['char'] in SENTENCE_END_PUNCTUATION  # Punctuation
        and tokens[index + 2]['char'] == '\n'  # Newline
        and tokens[index + 1]['color'] == 'normal'
        and tokens[index + 2]['color'] == 'normal'
    )

def create_blocks(tokens):
    """
    Create replacement and insertion blocks from tokenized text.

    Args:
        tokens (List[Dict]): Tokenized text from the tokenizer.

    Returns:
           List[Union[ReplacementBlock, InsertionBlock, PinkBlock]]: List of created blocks.
    """

    blocks = []
    i = 0

    while i < len(tokens):
        # Replacement Block (red + green)
        if tokens[i]['color'] == 'red':
            anchor_point = i
            red_text = ""
            replacement_text = ""
            red_end = None

            # Debug: Print replacement block start
            print(f"Starting replacement block at index {anchor_point}")

            # Collect red text
            while i < len(tokens) and tokens[i]['color'] == 'red':
                red_text += tokens[i]['char']
                red_end = i
                i += 1

            # Collect green text (if any) and remove it
            if i < len(tokens) and tokens[i]['color'] == 'green':
                green_start = i
                while i < len(tokens) and tokens[i]['color'] == 'green':
                    replacement_text += tokens[i]['char']
                    i += 1

                # Debug: Print collected green text
                print(f"Collected green text: '{replacement_text}'")

                # Remove green text from tokens
                del tokens[green_start:i]
                i = green_start  # Reset i to account for removed tokens
                

            # Create replacement block
            blocks.append(ReplacementBlock(anchor_point, red_end, red_text, replacement_text))

        # Insertion Block (blue only)
        elif tokens[i]['color'] == 'blue':
            anchor_point = i
            insert_text  = ""
            start_index = i  # Save starting index for debugging

            # Debug: Print insertion block start
            print(f"Starting insertion block at index {anchor_point}")

            # Collect blue text
            while i < len(tokens) and tokens[i]['color'] == 'blue':
                insert_text += tokens[i]['char']
                i += 1

            if len(insert_text ) == 1 and insert_text  in [',', '.', ';', ':', '!', '?', "'", '"']:
                print(f"Skipping isolated blue punctuation '{insert_text }' at index {start_index}.")
                continue  # Skip isolated punctuation

            # Check if the blue block ends the sentence
            if is_sentence_end(tokens, i - 1):
                print(f"Skipping insertion block at index {anchor_point} as it ends the sentence.")
                continue
            # Valid blue block: Create insertion block and handle tokens
            blocks.append(InsertionBlock(anchor_point, insert_text))
            print(f"Created insertion block: {vars(blocks[-1])}")

            # Remove blue text from tokens
            blue_start = anchor_point
            del tokens[blue_start:i]

            # Insert a space at the original anchor point to maintain alignment
            tokens.insert(blue_start, {'index': blue_start, 'char': ' ', 'color': 'normal'})

        elif tokens[i]['color'] == 'pink':
            anchor_point = i
            print(f"Starting pink block at index {anchor_point}")

            # Skip over contiguous pink tokens
            while i < len(tokens) and tokens[i]['color'] == 'pink':
                i += 1

            # Create a pink block
            blocks.append(PinkBlock(anchor_point))
            print(f"Created pink block: {vars(blocks[-1])}")

        elif tokens[i]['char'] == '\n' and i + 1 < len(tokens) and tokens[i + 1]['char'] == '\n':
            # Create a SentenceEndBlock instance
            anchor_point = i
            blocks.append(SentenceEndBlock(anchor_point))
            print(f"Created sentence_end block: {vars(blocks[-1])}")
            i += 2  # Skip both newline characters

        else:
            
            i += 1

    for j in range(len(blocks) - 1):
        current_block = blocks[j]
        next_block = blocks[j + 1]

        # Use red_end for ReplacementBlock; use anchor_point for InsertionBlock
        current_block_end = (
            current_block.red_end
            if hasattr(current_block, 'red_end')
            else current_block.anchor_point
        )

        # Measure distance from current_block_end to the next block's anchor_point
        if hasattr(next_block, 'anchor_point'):
            distance = next_block.anchor_point - current_block_end
        else:
            # Skip blocks without anchor_point (e.g., if any new block type is added without anchor_point)
            continue


        # Ensure distance is more than 3 and less than or equal to 8
        if 3 < distance <= 19:
            # Mark as eligible
            current_block.ride_along_eligible = True
            current_block.ride_along_end = next_block.anchor_point
            print(f"Ride-along eligible: Block End={current_block_end}, RideAlongEnd={current_block.ride_along_end}")
        else:
            # Log blocks not eligible
            reason = (
                f"Distance too small: {distance}" if distance <= 3 else f"Distance too large: {distance}"
            )
            print(f"Not eligible: Block End={current_block_end}, Next Block Anchor={next_block.anchor_point}, Reason: {reason}")

    # Debug: Print created blocks
    print("\nCreated Blocks:")
    for block in blocks:
        print(vars(block))

    return blocks

