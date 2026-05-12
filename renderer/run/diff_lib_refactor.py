import re
import difflib
from typing import List, Tuple, Dict
from seq_alignment_reverse import align_sentences
import pickle
from utils import apply_colors


COMBINATION_MARKER = "^**^"
HYPHEN_LIKE_CHARS = {"-", "‑", "–", "—", "‒", "−"}


def remove_combination_marker(tokens: List[Dict[str, str]], marker: str) -> List[Dict[str, str]]:
    """
    Remove tokens matching the COMBINATION_MARKER from the token list.
    Handles cases where the marker spans multiple tokens.
    """
    marker_chars = list(marker)  # ['^', '*', '*', '^']
    filtered_tokens = []
    i = 0

    while i < len(tokens):
        # Check if the current slice matches the marker
        if (
            i + len(marker_chars) <= len(tokens) and
            all(tokens[i + j]['char'] == marker_chars[j] for j in range(len(marker_chars))) 
        ):
            # Skip the entire marker span
            i += len(marker_chars)
        else:
            filtered_tokens.append(tokens[i])
            i += 1

    return filtered_tokens


def tokenize(text: str) -> List[str]:
    """
    Tokenize text into words, spaces, and punctuation.
    """
    return re.findall(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)*|\.\w+|[.,!?;:]+|\s+|[^\w\s]", text)


def normalize_apostrophes(text: str) -> str:
    """
    Replace curly and inconsistent apostrophes with straight apostrophes for consistent tokenization.
    """
    return (text.replace('‘', "'")
                .replace('’', "'")
                .replace('‛', "'")
                .replace('`', "'")
                .replace('´', "'"))


def normalize_intraword_quote_apostrophes(text: str) -> str:
    """
    Convert quote artifacts that are functioning as apostrophes without touching real quotation marks.
    """
    text = re.sub(r'(?<=\w)"(?=\w)', "'", text)
    return re.sub(r'(\b\w+s)"(?=\s+[A-Za-z])', r"\1'", text)


def align_and_tokenize(original: List[str], corrected: List[str]) -> List[Dict[str, str]]:
    """
    Align tokens between original and corrected sentences and assign types:
    - 'equal', 'replace', 'corrected', 'delete', 'insert'
    """
    sm = difflib.SequenceMatcher(None, original, corrected)
    word_level_tokens = []

    # Iterate over opcodes which indicate how to transform original into corrected
    # tag can be 'equal', 'replace', 'delete', 'insert'
    # (i1, i2) -> range in original, (j1, j2) -> range in corrected
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            # Original and corrected are identical in this range
            word_level_tokens.extend({'char': t, 'type': 'equal'} for t in corrected[j1:j2])
        elif tag == 'replace':
            orig_segment = original[i1:i2]
            corr_segment = corrected[j1:j2]

            # Treat whitespace->single hyphen-like replacement as insertion.
            if (
                "".join(orig_segment).isspace()
                and len(corr_segment) == 1
                and corr_segment[0] in HYPHEN_LIKE_CHARS
            ):
                # Drop the original whitespace for this opcode and surface hyphen as insert.
                word_level_tokens.extend({'char': t, 'type': 'insert'} for t in corr_segment)
                continue

            # Original differs, first replaced segment is 'replace' type, 
            # corrected segment is 'corrected' type
            word_level_tokens.extend({'char': t, 'type': 'replace'} for t in orig_segment)
            word_level_tokens.extend({'char': t, 'type': 'corrected'} for t in corr_segment)
        elif tag == 'delete':
            # Tokens exist only in original
            word_level_tokens.extend({'char': t, 'type': 'delete'} for t in original[i1:i2])
        elif tag == 'insert':
            # Tokens exist only in corrected
            word_level_tokens.extend({'char': t, 'type': 'insert'} for t in corrected[j1:j2])

    # Now we have a list of tokens at a word/punctuation/space level.
    # We need to break them down into character-level tokens to match the original granularity.

    char_level_tokens = []
    index_counter = 0
    for token in word_level_tokens:
        text_segment = token['char']
        token_type = token['type']
        # Break each token into individual characters
        for c in text_segment:
            char_level_tokens.append({'index': index_counter, 'char': c, 'type': token_type})
            index_counter += 1

    # Inherit type for spaces between tokens of the same type (mimicking old color-space logic)
    for i in range(1, len(char_level_tokens) - 1):
        current_token = char_level_tokens[i]
        prev_token = char_level_tokens[i - 1]
        next_token = char_level_tokens[i + 1]
        if current_token['char'] == ' ' and prev_token['type'] == next_token['type'] and prev_token['type'] != 'equal':
            current_token['type'] = prev_token['type']

    return char_level_tokens


def highlight_changes(original: str, corrected: str) -> List[Dict[str, str]]:
    """
    Highlight differences between original and corrected sentences by producing typed, character-level tokens.

    Possible Improvements:
    - Rename highlight_changes to something more explicit, like get_aligned_tokens_with_types(), 
      to clarify it returns typed tokens instead of colored text.
    - Add more docstring details about what tokenize() returns and how align_and_tokenize() uses these tokens.
      For example, tokenize() returns a list of tokens (words/spaces/punctuation) which align_and_tokenize() 
      then processes to identify differences.
    - Consider adding inline comments or examples for clarity.
    """
    original = normalize_intraword_quote_apostrophes(normalize_apostrophes(original))
    corrected = normalize_intraword_quote_apostrophes(normalize_apostrophes(corrected))
    orig_tokens = tokenize(original)   # returns a list of word/punctuation/space tokens
    corr_tokens = tokenize(corrected)  # same as above

    # align_and_tokenize now returns character-level tokens with assigned types.
    return align_and_tokenize(orig_tokens, corr_tokens)



def generate_report(matches: List[Tuple[str, str]]) -> Tuple[str, List[List[Dict[str, str]]]]:
    """
    Generate a report of changes with sentence numbers.
    Tokenize the differences, remove combination markers, then apply colors for display.
    """
    report_lines = []
    tokenized_output = []

    for num, item in enumerate(matches, start=1):
        if isinstance(item, dict):
            original = item.get("ocr_sentence", "")
            corrected = item.get("corrected_sentence", "")
        else:
            original, corrected = item
        # Get typed tokens for differences
        tokens = highlight_changes(original, corrected)
        

        # Remove combination marker
        filtered_tokens = remove_combination_marker(tokens, COMBINATION_MARKER)

        # Convert to colored text for display
        cleaned_highlighted = apply_colors(filtered_tokens)

        report_lines.append(f"Sentence {num}:\n{cleaned_highlighted}")
        tokenized_output.append(filtered_tokens)

    return "\n\n".join(report_lines), tokenized_output


def process_text(ocr_text: str, corrected_text: str):
    print("Aligning sentences...")
    matches = align_sentences(ocr_text, corrected_text)

    print("\nGenerating report...")
    formatted_report, tokenized_output = generate_report(matches)
    print("\nFormatted Report:")
    print(formatted_report)

    with open("tokenized_output.pkl", "wb") as f:
        pickle.dump(tokenized_output, f)
    print("tokenized_output saved to tokenized_output.pkl")

    return formatted_report


if __name__ == "__main__":
    ocr_text = "Actually when I was touring around Southeast Asia, I didn't have enough time and money so, I couldn't go to Bali."
    corrected_text = "When I was touring around Southeast Asia, I didn’t have enough time or money.^``^ So I couldn’t go to Bali."
    
    process_text(ocr_text, corrected_text)
