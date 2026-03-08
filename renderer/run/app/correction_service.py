import json
import os
import sys
import copy
import string
import re

# Paths (adjust as needed)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SENTENCE_MAPPING_PATH = os.path.join(BASE_DIR, "sentence_mapping.json")
OUTPUT_JSON_PATH = os.path.join(os.path.dirname(__file__), "output.json")

# --- Configurable Isolated Punctuation Rules ---

# Default set of punctuation characters to consider
CUSTOM_ISOLATED_PUNCTUATION = set(string.punctuation)  # You can update this later.
# Custom sequences (tuples of characters) that count as isolated (e.g. double periods)
CUSTOM_SEQUENCES = {("..",), ("...",)}

def update_isolated_punctuation_rules(new_punctuation_set=None, new_sequences=None):
    """
    Update the rules for isolated punctuation.
    Args:
        new_punctuation_set (set): New set of punctuation characters.
        new_sequences (set): New set of tuples representing punctuation sequences.
    """
    global CUSTOM_ISOLATED_PUNCTUATION, CUSTOM_SEQUENCES
    if new_punctuation_set is not None:
        CUSTOM_ISOLATED_PUNCTUATION = set(new_punctuation_set)
    if new_sequences is not None:
        CUSTOM_SEQUENCES = set(new_sequences)
    print("DEBUG: Updated isolated punctuation rules:")
    print("  Characters:", CUSTOM_ISOLATED_PUNCTUATION)
    print("  Sequences:", CUSTOM_SEQUENCES)

def is_isolated_punctuation(token, token_list):
    """
    Determines if a token is isolated punctuation.
    A token is isolated if its character is in the CUSTOM_ISOLATED_PUNCTUATION set and 
    both its previous and next tokens (if any) are punctuation or spaces,
    or if it is part of a custom sequence defined in CUSTOM_SEQUENCES.
    """
    index = token["index"]
    char = token["char"]
    if char not in CUSTOM_ISOLATED_PUNCTUATION:
        return False
    prev_token = token_list[index - 1] if index > 0 else None
    next_token = token_list[index + 1] if index + 1 < len(token_list) else None
    prev_ok = (prev_token is None) or (prev_token["char"] in CUSTOM_ISOLATED_PUNCTUATION or prev_token["char"] == " ")
    next_ok = (next_token is None) or (next_token["char"] in CUSTOM_ISOLATED_PUNCTUATION or next_token["char"] == " ")
    surrounding = "".join(token_list[i]["char"] for i in range(max(0, index - 1), min(len(token_list), index + 2)))
    sequence_found = any("".join(seq) in surrounding for seq in CUSTOM_SEQUENCES)
    return (prev_ok and next_ok) or sequence_found

def get_ocr_sentence_if_isolated(correction_entry, clicked_delete_block_id):
    """
    If any delete token (for the clicked block) is isolated punctuation, load and return the OCR sentence.
    Otherwise, return None.
    """
    tokens = correction_entry.get("final_sentence_tokens", [])
    for token in tokens:
        if token.get("type") == "delete" and int(token.get("deleteBlockId", -1)) == int(clicked_delete_block_id):
            if is_isolated_punctuation(token, tokens):
                print(f"\n--- DEBUG: Isolated punctuation detected ('{token['char']}') at index {token['index']} ---")
                if not os.path.exists(SENTENCE_MAPPING_PATH):
                    print(f"ERROR: {SENTENCE_MAPPING_PATH} not found.")
                    return {"error": "Sentence mapping file not found"}
                try:
                    with open(SENTENCE_MAPPING_PATH, "r", encoding="utf-8") as f:
                        sentence_mapping = json.load(f)
                    sentence_index = correction_entry.get("sentence_index")
                    sentence_entry = next((s for s in sentence_mapping.get("sentences", [])
                                           if s.get("sentence_index") == sentence_index), None)
                    if sentence_entry:
                        print("\n--- DEBUG: Returning OCR sentence due to isolated punctuation ---")
                        return sentence_entry.get("ocr_sentence", "")
                    else:
                        print(f"ERROR: No sentence found in mapping for index {sentence_index}")
                        return {"error": "OCR sentence not found"}
                except Exception as e:
                    print("ERROR: Failed to load sentence mapping:", str(e))
                    return {"error": "JSON load error", "details": str(e)}
    return None

# --- Standard Functions ---



def _build_corrected_sentence_from_entry(correction_entry):
    """Reconstruct a corrected sentence directly from token data + replacement blocks."""
    source_tokens = [copy.deepcopy(t) for t in correction_entry.get("final_sentence_tokens", [])]
    replacement_blocks = correction_entry.get("replacement_blocks", []) or []
    spans = _compute_replacement_spans(source_tokens, replacement_blocks)
    tokens = _apply_replacements_with_spans([copy.deepcopy(t) for t in source_tokens], spans)
    # Deleted chars should not appear in corrected sentence.
    tokens = [t for t in tokens if t.get("type") != "delete"]
    return _sentence_from_tokens(tokens)


def _build_original_sentence_from_entry(correction_entry):
    """Reconstruct a baseline sentence from final_sentence_tokens without mapping."""
    tokens = list(correction_entry.get("final_sentence_tokens", []))
    original_sentence = "".join(t.get("char", "") for t in tokens)
    return " ".join(original_sentence.split())


def _sentence_from_tokens(tokens):
    sentence = "".join(t.get("char", "") for t in tokens)
    sentence = " ".join(sentence.split())
    return _normalize_intraword_double_quotes(sentence)


def _find_replacement_token_range(tokens, block):
    """
    Find the token range for a replacement block using replacementBlockId.
    Falls back to final_start/final_end when ids are unavailable.
    """
    block_id = block.get("block_index")
    indices = [
        i for i, t in enumerate(tokens)
        if t.get("replacementBlockId") == block_id
    ]
    if indices:
        return min(indices), max(indices)

    start = block.get("final_start")
    end = block.get("final_end")
    if isinstance(start, int) and isinstance(end, int) and start <= end:
        return start, end
    return None


def _compute_replacement_spans(source_tokens, replacement_blocks):
    """
    Compute replacement spans once from source tokens.
    Returned spans use source-token coordinates.
    """
    spans = []
    for block in replacement_blocks:
        span = _find_replacement_token_range(source_tokens, block)
        if span is None:
            continue
        start, end = span
        spans.append({
            "block_index": block.get("block_index"),
            "start": start,
            "end": end,
            "corrected_text": block.get("corrected_text", ""),
        })
    return spans


def _apply_replacements_with_spans(tokens, spans, skip_block_index=None):
    """
    Apply replacements right-to-left using precomputed source spans.
    This avoids index-shift corruption for length-changing edits.
    """
    for item in sorted(spans, key=lambda s: s["start"], reverse=True):
        block_id = item.get("block_index")
        if skip_block_index is not None and block_id == skip_block_index:
            continue
        start = item["start"]
        end = item["end"]
        replacement_text = item.get("corrected_text", "")
        new_tokens = [{"char": ch, "type": "equal"} for ch in replacement_text]
        tokens = tokens[:start] + new_tokens + tokens[end + 1:]
    return tokens


def build_before_after_for_clicked_block(correction_entry, correction_block, block_type):
    """
    Build consistent model context for all block types.
    AFTER: fully corrected sentence.
    BEFORE: same sentence, but with only the clicked block inverted.
    """
    final_tokens = [copy.deepcopy(t) for t in correction_entry.get("final_sentence_tokens", [])]
    replacement_blocks = correction_entry.get("replacement_blocks", []) or []
    replacement_spans = _compute_replacement_spans(final_tokens, replacement_blocks)

    # AFTER: all corrections applied.
    after_tokens = _apply_replacements_with_spans([copy.deepcopy(t) for t in final_tokens], replacement_spans)
    after_tokens = [t for t in after_tokens if t.get("type") != "delete"]
    after_sentence = _sentence_from_tokens(after_tokens)

    # BEFORE: apply all corrections except the clicked one inversion.
    before_tokens = [copy.deepcopy(t) for t in final_tokens]
    if block_type == "replacement":
        clicked_block_id = correction_block.get("block_index")
        before_tokens = _apply_replacements_with_spans(
            before_tokens, replacement_spans, skip_block_index=clicked_block_id
        )
        before_tokens = [t for t in before_tokens if t.get("type") != "delete"]
    elif block_type == "insert":
        clicked_insert_id = int(correction_block.get("insert_block_index"))
        before_tokens = _apply_replacements_with_spans(before_tokens, replacement_spans)
        before_tokens = [
            t for t in before_tokens
            if not (t.get("type") == "insert" and int(t.get("insertBlockId", -1)) == clicked_insert_id)
        ]
        before_tokens = [t for t in before_tokens if t.get("type") != "delete"]
    elif block_type == "delete":
        clicked_delete_id = int(correction_block.get("delete_block_index"))
        before_tokens = _apply_replacements_with_spans(before_tokens, replacement_spans)
        before_tokens = [
            t for t in before_tokens
            if not (t.get("type") == "delete" and int(t.get("deleteBlockId", -1)) != clicked_delete_id)
        ]
    else:
        raise ValueError(f"UNSUPPORTED BLOCK TYPE: {block_type}")

    before_sentence = _sentence_from_tokens(before_tokens)
    return before_sentence, after_sentence


def _normalize_intraword_double_quotes(text):
    """
    Normalize only apostrophe-like double quotes inside words.
    Examples:
      one"s -> one's
      students" health -> students' health
    """
    normalized = text or ""
    # Contraction/possessive inside a word.
    normalized = re.sub(r'(?<=\w)"(?=\w)', "'", normalized)
    # Plural possessive artifact before a following word.
    normalized = re.sub(r'(\b\w+s)"(?=\s+[A-Za-z])', r"\1'", normalized)
    return normalized

def get_correction_explanation(data):
    print("DEBUG: Function get_correction_explanation() was called")
    print("DEBUG: Received data:", data)
    sys.stdout.flush()
    try:
        block_type = data['blockType']
        block_index = int(data['blockIndex'])
        sentence_index = int(data['sentenceIndex'])
    except Exception as e:
        print("DEBUG: Input parsing error:", e)
        return {"error": "Invalid input", "details": str(e)}
    sentence_mapping = {"sentences": []}
    if not os.path.exists(SENTENCE_MAPPING_PATH):
        print(f"WARN: {SENTENCE_MAPPING_PATH} does not exist; using token-based sentence fallback")
    if not os.path.exists(OUTPUT_JSON_PATH):
        print(f"ERROR: {OUTPUT_JSON_PATH} does not exist")
        return {"error": "Output file not found"}
    try:
        if os.path.exists(SENTENCE_MAPPING_PATH):
            with open(SENTENCE_MAPPING_PATH, "r", encoding="utf-8") as f:
                sentence_mapping = json.load(f)
        with open(OUTPUT_JSON_PATH, "r", encoding="utf-8") as f:
            output_data = json.load(f)
        print(f"DEBUG: Loaded {len(sentence_mapping.get('sentences', []))} sentences")
        print(f"DEBUG: Loaded {len(output_data.get('sentences', []))} corrections")
    except Exception as e:
        print("DEBUG: Error loading JSON files:", e)
        return {"error": "JSON load error", "details": str(e)}
    sentence_entry = next((s for s in sentence_mapping.get("sentences", [])
                           if s.get("sentence_index") == sentence_index), None)
    if sentence_entry:
        print(f"DEBUG: Found sentence {sentence_entry.get('ocr_sentence')}")
    else:
        print(f"WARN: No sentence mapping found for index {sentence_index}; using token fallback")
    correction_entry = next((c for c in output_data.get("sentences", [])
                             if c.get("sentence_index") == sentence_index), None)
    if not correction_entry:
        print(f"DEBUG: No correction found for index {sentence_index}")
        return {"error": "Corrections not found", "sentence_index": sentence_index}
    block_key = f"{block_type}_blocks"
    if block_key not in correction_entry:
        print(f"DEBUG: Block type '{block_type}' not found")
        return {"error": "Invalid block type", "block_type": block_type}
    try:
        if block_type == "delete":
            correction_block = next((b for b in correction_entry[block_key]
                                     if b.get("delete_block_index", -1) == block_index), None)
        elif block_type == "insert":
            correction_block = next((b for b in correction_entry[block_key]
                                     if b.get("insert_block_index", -1) == block_index), None)
        else:
            correction_block = next((b for b in correction_entry[block_key]
                                     if b.get("block_index", -1) == block_index), None)
    except Exception as e:
        print(f"DEBUG: Error extracting block: {e}")
        return {"error": "Block index error", "details": str(e)}
    if not correction_block:
        print(f"DEBUG: No block found for type {block_type} at index {block_index}")
        return {"error": f"{block_type.capitalize()} block not found", "block_index": block_index}
    print("DEBUG: Correction block found:", correction_block)
    print("DEBUG: Correction entry keys:", list(correction_entry.keys()))
    print("DEBUG: final_sentence_tokens:", correction_entry.get("final_sentence_tokens"))

    mapped_ocr = sentence_entry.get("ocr_sentence", "") if sentence_entry else ""
    mapped_corrected = sentence_entry.get("corrected_sentence", "") if sentence_entry else ""
    mapped_ocr = _normalize_intraword_double_quotes(mapped_ocr)
    mapped_corrected = _normalize_intraword_double_quotes(mapped_corrected)
    replaced_text = correction_block.get("replaced_text", "")
    corrected_text = correction_block.get("corrected_text", "")

    local_ocr = _normalize_intraword_double_quotes(_build_original_sentence_from_entry(correction_entry))
    local_corrected = _normalize_intraword_double_quotes(_build_corrected_sentence_from_entry(correction_entry))

    use_local_ocr = not mapped_ocr or (replaced_text and replaced_text not in mapped_ocr)
    use_local_corrected = not mapped_corrected or (corrected_text and corrected_text not in mapped_corrected)

    if use_local_ocr:
        print("WARN: Using token-based OCR sentence fallback due to missing/mismatched mapping sentence")
    if use_local_corrected:
        print("WARN: Using token-based corrected sentence fallback due to missing/mismatched mapping sentence")

    return {
        "ocr_sentence": local_ocr if use_local_ocr else mapped_ocr,
        "corrected_sentence": local_corrected if use_local_corrected else mapped_corrected,
        "correction_block": copy.deepcopy(correction_block),
        "correction_entry": copy.deepcopy(correction_entry)
    }

def generate_custom_sentence_for_block(correction_entry, correction_block, block_type):
    """
    Rebuilds the custom (incorrect) sentence using final_sentence_tokens.
    For replacement blocks, applies corrections for all non-clicked blocks while leaving the
    clicked block's tokens (showing the error) unchanged.
    For insert blocks, removes tokens in the clicked range.
    For delete blocks, no further modification is needed.
    Finally, all tokens flagged as delete (from any delete block) are removed.
    """
    tokens = list(correction_entry.get("final_sentence_tokens", []))
    
    if block_type == "replacement":
        clicked_block_id = correction_block.get("block_index")
        # Apply corrections for non-clicked replacement blocks.
        for block in correction_entry.get("replacement_blocks", []):
            if block.get("block_index") != clicked_block_id:
                start = block.get("final_start")
                corrected_text = block.get("corrected_text", "")
                replaced_text = block.get("replaced_text", "")
                original_span = len(replaced_text)
                print(f"DEBUG: [Tokens] Non-clicked Replacement block (id {block.get('block_index')}): start={start}, corrected_text='{corrected_text}', replaced_text='{replaced_text}'")
                for i, ch in enumerate(corrected_text):
                    pos = start + i
                    if pos < len(tokens):
                        tokens[pos]["char"] = ch
                # Clear extra tokens if corrected_text is shorter.
                for pos in range(start + len(corrected_text), start + original_span):
                    if pos < len(tokens):
                        tokens[pos]["char"] = ""
    
    elif block_type == "insert":
        start = correction_block.get("final_start")
        end = correction_block.get("final_end")
        print(f"DEBUG: [Tokens] Insert block: Removing tokens from index {start} to {end} (inclusive)")
        tokens = [token for i, token in enumerate(tokens) if not (i >= start and i <= end)]
    
    elif block_type == "delete":
        print("DEBUG: [Tokens] Delete block: No additional token modification needed")
    
    # Remove all tokens flagged as delete to reduce noise.
    tokens = [token for token in tokens if token.get("type") != "delete"]
    
    custom_sentence = "".join(token["char"] for token in tokens)
    # Trim extra spaces that may occur.
    custom_sentence = " ".join(custom_sentence.split())
    print("DEBUG: [Tokens] Custom sentence after all modifications:", custom_sentence)
    return custom_sentence


# --- For Delete Blocks: Rebuild Without Processing Insert Tokens ---
def rebuild_sentence_for_delete(correction_entry, clicked_delete_block_id):
    tokens = correction_entry.get("final_sentence_tokens", [])
    replacement_blocks = correction_entry.get("replacement_blocks", [])
    print("\n--- DEBUG: ORIGINAL TOKENS (Ignoring Inserts) ---")
    for token in tokens:
        print(f"INDEX {token['index']} | TYPE: {token.get('type','')} | CHAR: '{token['char']}'")
    
    tokens_sorted = sorted(tokens, key=lambda t: t.get("index", 0))
    working_tokens = list(tokens_sorted)

    for rep in replacement_blocks:
        start = rep.get("final_start")
        corrected_text = rep.get("corrected_text", "")
        replaced_text = rep.get("replaced_text", "")
        original_span = len(replaced_text)
        print(f"\n--- DEBUG: Processing Replacement Block at index {start} ---")
        print(f"Corrected text: '{corrected_text}' (len={len(corrected_text)})")
        print(f"Replaced text:  '{replaced_text}' (len={original_span})")
        for i, ch in enumerate(corrected_text):
            pos = start + i
            if pos < len(working_tokens):
                print(f"Before: Token at pos {pos} = '{working_tokens[pos]['char']}'")
                working_tokens[pos]["char"] = ch
                print(f"After:  Token at pos {pos} = '{working_tokens[pos]['char']}'")
        for pos in range(start + len(corrected_text), start + original_span):
            if pos < len(working_tokens):
                print(f"Blanking out token at pos {pos} (was '{working_tokens[pos]['char']}')")
                working_tokens[pos]["char"] = ""
    
    print("\n--- DEBUG: TOKENS AFTER REPLACEMENT (Ignoring Inserts) ---")
    for token in working_tokens:
        print(f"INDEX {token.get('index','?')} | TYPE: {token.get('type','')} | CHAR: '{token.get('char','')}'")
    
    clicked_delete_block_id = int(clicked_delete_block_id)
    final_tokens = [
        token for token in working_tokens
        if not (token.get("type") == "delete" and int(token.get("deleteBlockId", -1)) != clicked_delete_block_id)
    ]
    
    print("\n--- DEBUG: FINAL TOKENS (After Filtering Deletes) ---")
    for token in final_tokens:
        print(f"INDEX {token.get('index','?')} | TYPE: {token.get('type','')} | CHAR: '{token.get('char','')}'")
    
    final_sentence = "".join(token["char"] for token in final_tokens)
    print("\n--- DEBUG: FINAL REBUILT SENTENCE (No Inserts) ---")
    print(final_sentence)
    return final_sentence

# --- Main Entry for Standalone Testing ---
if __name__ == "__main__":
    # Adjust test_data as needed for deletion, insertion, or replacement blocks.
    test_data = {"blockType": "replacement", "blockIndex": 0, "sentenceIndex": 0}
    print("DEBUG: Running manual test")
    result = get_correction_explanation(test_data)
    print("DEBUG: Correction Info:", result)
    if "error" not in result:
        # For tokens-based rebuild, we use generate_custom_sentence_for_block_tokens.
        block_type = test_data["blockType"]
        correction_entry = result.get("correction_entry")
        correction_block = result["correction_block"]
        custom_sentence = generate_custom_sentence_for_block(correction_entry, correction_block, block_type)
        print("\n--- Custom Sentence (Correction Reverted) ---")
        print(custom_sentence)
