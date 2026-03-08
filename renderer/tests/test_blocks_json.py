import json
from block_creation import create_blocks  # Import your block creation logic

def process_tokenized_sentences(input_file, output_file):
    """
    Process tokenized sentences with color codes to create block objects and save both tokens and blocks.
    """
    # Step 1: Load the tokenized sentences from JSON
    with open(input_file, "r", encoding="utf-8") as f:
        tokenized_data = json.load(f)

    processed_data = []

    # Step 2: Iterate over tokenized sentences
    for item in tokenized_data:
        pair_index = item["pair_index"]  # Unique identifier for each sentence
        tokens = item["tokens"]  # List of tokens with color codes

        # Step 3: Create blocks from tokens
        blocks = create_blocks(tokens)

        # Step 4: Convert blocks to dictionaries for JSON serialization
        block_dicts = []
        for block in blocks:
            if block.type == 'replace':
                block_dicts.append({
                    "type": "replace",
                    "anchor": block.anchor_point,
                    "red_end": block.red_end,
                    "incorrect_text": block.red_text,
                    "correct_text": block.replacement_text,
                    "ride_along_eligible": block.ride_along_eligible,
                    "ride_along_end": block.ride_along_end,
                })
            elif block.type == 'insert':
                block_dicts.append({
                    "type": "insert",
                    "anchor": block.anchor_point,
                    "correct_text": block.insert_text,
                    "ride_along_eligible": block.ride_along_eligible,
                    "ride_along_end": block.ride_along_end,
                })

        # Step 5: Append the sentence index, tokens, and blocks to the processed data
        processed_data.append({
            "sentence_index": pair_index,
            "tokenized_text": tokens,
            "blocks": block_dicts
        })

    # Step 6: Save all processed data into a JSON file
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(processed_data, f, ensure_ascii=False, indent=4)

    print(f"Processed data saved to '{output_file}'.")

# Example usage
if __name__ == "__main__":
    process_tokenized_sentences(
        input_file="tokenized_outputs.json",
        output_file="processed_data.json"
    )
