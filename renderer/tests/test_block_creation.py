import sys
sys.path.append('/home/keithuncouth/red_pen_app/renderer')  # Adjust path to your `renderer` directory

from tokenizer import TextTokenizer  # Tokenizer logic from tokenizer.py
from block_creation import create_blocks  # Block creation logic from block_creation.py
from script_runner import generate_report_from_script  # Runs DiffLib parser script

ANSI_COLORS = {
    'normal': '\033[0m',  # Default
    'red': '\033[31m',    # Red
    'blue': '\033[34m',   # Blue
    'green': '\033[32m',  # Green
    'pink': '\033[35m',   # Pink
}

def test_block_creation():
    """
    Test the block creation logic using the tokenizer output.
    """
    # Step 1: Generate raw text using the DiffLib parser output
    raw_output = generate_report_from_script()

    if not raw_output.strip():
        print("Error: No output from sentence_parse.py")
        return

    # Step 2: Tokenize the raw output
    tokenizer = TextTokenizer(raw_output)
    tokens = tokenizer.parse_text()

    # Step 3: Create blocks from tokens
    blocks = create_blocks(tokens)

    # Step 4: Print the blocks for verification
    print("\nGenerated Blocks:")
    for block in blocks:
        if block.type == 'replace':
            print(f"ReplaceBlock: Anchor={block.anchor_point}, RedEnd={block.red_end}, "
                  f"IncorrectText='{block.red_text}', CorrectText='{block.replacement_text}', "
                  f"RideAlongEligible={block.ride_along_eligible}, RideAlongEnd={block.ride_along_end}")
        elif block.type == 'insert':
            print(f"InsertBlock: Anchor={block.anchor_point}, CorrectText='{block.insert_text}', "
                  f"RideAlongEligible={block.ride_along_eligible}, RideAlongEnd={block.ride_along_end}")

    # Step 5: Print the final tokens list
    print("\nFinal Tokens List:")
    for idx, token in enumerate(tokens):
        print(f"Index={idx}, Char='{token['char']}', Color={token['color']}")


    # Step 7: Render the final sentence with ANSI colors
    final_sentence = ''.join(
        f"{ANSI_COLORS.get(token['color'], '')}{token['char']}" for token in tokens
    )
    final_sentence += '\033[0m'  # Reset color at the end

    print("\nFinal Sentence with ANSI Colors:")
    print(final_sentence)


if __name__ == "__main__":
    test_block_creation()