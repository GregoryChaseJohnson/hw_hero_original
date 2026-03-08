import json
import sys

from tokenizer import TextTokenizer  # Import tokenizer prototype

def test_tokenizer():
    # Load the JSON file containing fused differences
    with open("fused_differences.json", "r", encoding="utf-8") as f:
        fused_differences = json.load(f)
    
    # Ensure the file is not empty
    if not fused_differences:
        print("Error: No content found in 'fused_differences.json'.")
        return

    # Initialize a list to hold tokenized outputs
    tokenized_outputs = []

    # Iterate over fused differences and tokenize each
    for index, fused_text in enumerate(fused_differences, start=1):
        print(f"Processing sentence pair {index}:")
        tokenizer = TextTokenizer(fused_text)
        tokens = tokenizer.parse_text()
        tokenized_outputs.append({"pair_index": index, "tokens": tokens})

    # Save all tokenized outputs to a single JSON file
    with open("tokenized_outputs.json", "w", encoding="utf-8") as f:
        json.dump(tokenized_outputs, f, ensure_ascii=False, indent=4)

    print("Tokenized outputs saved to 'tokenized_outputs.json'.")

if __name__ == "__main__":
    test_tokenizer()
