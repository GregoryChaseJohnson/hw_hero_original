import json
import pickle
import re
from seq_alignment_reverse import split_into_sentences

def replace_double_quotes_in_tokens(tokens):
    """
    Replace double quotes used as apostrophes with single quotes in a list of tokens.
    Tokens are modified in place.
    """
    for token in tokens:
        token["char"] = re.sub(r'\b(\w+)"(\w+)\b', r"\1'\2", token["char"])
    return tokens

def compute_container_length(annotated_line, final_line):
    """
    Determine how wide the sentence container should be by finding
    the maximum index in both annotated_line and final_line,
    then adding 1 (assuming 0-based indexing, so +1 is total token count).
    """
    max_annotated_idx = max((t["index"] for t in annotated_line), default=0)
    max_final_idx = max((t["index"] for t in final_line), default=0)
    return max(max_annotated_idx, max_final_idx) + 1


def _sentence_spans_from_text(text):
    """
    Return character spans for sentence-like segments based on punctuation + capital boundary.
    Spans include trailing boundary spaces with the preceding sentence.
    """
    if not text:
        return [(0, 0)]
    pattern = re.compile(r'(?<=[.!?])["\'“”‘’]?\s+(?=[A-Z])')
    spans = []
    start = 0
    for m in pattern.finditer(text):
        end = m.end()
        if end > start:
            spans.append((start, end))
        start = end
    if start < len(text):
        spans.append((start, len(text)))
    return spans or [(0, len(text))]


def _slice_tokens_by_span(tokens, start, end):
    """
    Slice character tokens using [start, end) character positions and reindex from zero.
    """
    sliced = []
    for idx in range(start, min(end, len(tokens))):
        tok = dict(tokens[idx])
        tok["index"] = len(sliced)
        sliced.append(tok)
    return sliced


def _spans_overlap(start_a, end_a, start_b, end_b):
    return start_a < end_b and start_b < end_a


def _owned_annotated_slice(annotated_tokens, start, end, paired_blocks):
    """
    Slice annotated tokens for a final sentence span while preserving correction overhang.
    Corrected tokens from replacement blocks are owned by the final span their red block
    overlaps, not by whatever sentence span their visual position happens to fall in.
    """
    ann_end = end
    owned_ann_ranges = []
    for ann_block, fin_block in paired_blocks:
        fin_start = fin_block["start"]
        fin_end = fin_block["end"] + 1
        if _spans_overlap(fin_start, fin_end, start, end):
            ann_start = ann_block["start"]
            ann_stop = ann_block["end"] + 1
            ann_end = max(ann_end, ann_stop)
            owned_ann_ranges.append((ann_start, ann_stop))

    sliced = []
    for idx in range(start, min(ann_end, len(annotated_tokens))):
        tok = dict(annotated_tokens[idx])
        if tok.get("type") == "corrected":
            is_owned = any(range_start <= idx < range_end for range_start, range_end in owned_ann_ranges)
            if not is_owned:
                tok = {**tok, "char": " ", "type": "equal"}
        tok["index"] = len(sliced)
        sliced.append(tok)
    return sliced


def _normalize_sentence_text(text):
    return " ".join((text or "").split())


def _tokens_to_text(tokens):
    return _normalize_sentence_text("".join(t.get("char", "") for t in tokens))


def _copy_mapping_entry(mapping_entry):
    return dict(mapping_entry) if isinstance(mapping_entry, dict) else {}


def split_for_display(annotated_lines, final_sentences, sentence_mapping):
    """
    Split merged sentence units into single-sentence display containers.
    Keeps alignment quality from upstream merge/diff stages, then re-segments for UI.
    """
    mapping_entries = sentence_mapping.get("sentences", []) if isinstance(sentence_mapping, dict) else []
    split_annotated = []
    split_final = []
    split_mapping = {"sentences": []}
    existing_indices = [
        entry.get("sentence_index")
        for entry in mapping_entries
        if isinstance(entry, dict) and isinstance(entry.get("sentence_index"), int)
    ]
    next_idx = (max(existing_indices) + 1) if existing_indices else 0

    for i, (ann_line, fin_line) in enumerate(zip(annotated_lines, final_sentences)):
        final_text = "".join(t.get("char", "") for t in fin_line)
        mapping_entry = mapping_entries[i] if i < len(mapping_entries) else {}
        source_sentence_index = mapping_entry.get("sentence_index", i)

        if mapping_entry.get("is_combined_scope") or mapping_entry.get("correction_mode") in {"join", "split"}:
            split_final.append(fin_line)
            split_annotated.append(ann_line)
            new_mapping_entry = _copy_mapping_entry(mapping_entry)
            new_mapping_entry.update({
                "sentence_index": source_sentence_index,
                "source_sentence_index": source_sentence_index,
                "render_mode": "token_diff",
                "is_combined_scope": True,
            })
            split_mapping["sentences"].append(new_mapping_entry)
            continue

        spans = _sentence_spans_from_text(final_text)
        ann_blocks, fin_blocks = detect_replacement_blocks(ann_line, fin_line)
        paired_blocks = [
            (ann_block, fin_block)
            for ann_block, fin_block in zip(ann_blocks, fin_blocks)
            if ann_block.get("block_index") is not None and fin_block.get("block_index") is not None
        ]

        ocr_parts = split_into_sentences(mapping_entry.get("ocr_sentence", "")) if mapping_entry else []
        corr_parts = split_into_sentences(mapping_entry.get("corrected_sentence", "")) if mapping_entry else []
        use_ocr_parts = len(ocr_parts) == len(spans)
        use_corr_parts = len(corr_parts) == len(spans)

        for part_idx, (start, end) in enumerate(spans):
            fin_seg = _slice_tokens_by_span(fin_line, start, end)
            ann_seg = _owned_annotated_slice(ann_line, start, end, paired_blocks)
            split_final.append(fin_seg)
            split_annotated.append(ann_seg)

            if use_ocr_parts:
                ocr_sentence = _normalize_sentence_text(ocr_parts[part_idx])
            else:
                ocr_sentence = _tokens_to_text(fin_seg)

            if use_corr_parts:
                corrected_sentence = _normalize_sentence_text(corr_parts[part_idx])
            else:
                corrected_sentence = _tokens_to_text(fin_seg)

            new_mapping_entry = _copy_mapping_entry(mapping_entry)
            if len(spans) == 1 and part_idx == 0:
                sentence_index = source_sentence_index
            else:
                sentence_index = next_idx
            new_mapping_entry.update({
                "sentence_index": sentence_index,
                "source_sentence_index": source_sentence_index,
                "ocr_sentence": ocr_sentence,
                "corrected_sentence": corrected_sentence,
                "render_mode": new_mapping_entry.get("render_mode", "token_diff"),
                "is_combined_scope": bool(new_mapping_entry.get("is_combined_scope", False)),
            })
            split_mapping["sentences"].append(new_mapping_entry)
            next_idx += 1

    return split_annotated, split_final, split_mapping

def detect_blocks_by_type(tokens, valid_types=None):
    """
    General-purpose function to detect contiguous blocks of `valid_types`.
    Returns a list of dicts, each with "start", "end", "tokens", "block_index".
    """
    if valid_types is None:
        valid_types = {"replace"}  # default if nothing passed

    blocks = []
    block_start = None
    not_type_count = 0
    n = len(tokens)
    i = 0

    while i < n:
        ttype = tokens[i]["type"]
        if ttype in valid_types:
            not_type_count = 0
            if block_start is None:
                block_start = i
        else:
            not_type_count += 1
            if block_start is not None and not_type_count >= 2:
                end_idx = i - 2
                if end_idx >= block_start:
                    blocks.append({
                        "start": block_start,
                        "end": end_idx,
                        "tokens": tokens[block_start:end_idx + 1],
                        "block_index": None
                    })
                block_start = None
                not_type_count = 0
        i += 1

    if block_start is not None:
        blocks.append({
            "start": block_start,
            "end": n - 1,
            "tokens": tokens[block_start:],
            "block_index": None
        })

    return blocks

def assign_block_indices(annotated_blocks, final_blocks):
    """
    Assign indices only to overlapping blocks between annotated_blocks and final_blocks.
    This applies to replace/corrected pairs.
    """
    min_len = min(len(annotated_blocks), len(final_blocks))
    for idx in range(min_len):
        annotated_blocks[idx]["block_index"] = idx
        final_blocks[idx]["block_index"] = idx

def detect_replacement_blocks(annotated_tokens, final_tokens):
    """
    Detect matched `corrected` blocks in annotated_tokens and matched `replace` blocks in final_tokens.
    Then assign block indices.
    Returns a tuple (annotated_blocks, final_blocks).
    """
    ann_blocks = detect_blocks_by_type(annotated_tokens, valid_types={"corrected"})
    fin_blocks = detect_blocks_by_type(final_tokens, valid_types={"replace"})
    assign_block_indices(ann_blocks, fin_blocks)
    return ann_blocks, fin_blocks

def detect_insert_blocks(final_tokens):
    """
    Detect contiguous `insert` tokens in the final line.
    Assign an insert_block_index for reference.
    """
    blocks = detect_blocks_by_type(final_tokens, valid_types={"insert"})
    for idx, blk in enumerate(blocks):
        blk["block_index"] = idx  # use as insert block id
    return blocks

def detect_delete_blocks(final_tokens):
    """
    Detect contiguous `delete` tokens in the final line.
    Assign a delete_block_index for reference.
    """
    blocks = detect_blocks_by_type(final_tokens, valid_types={"delete"})
    for idx, blk in enumerate(blocks):
        blk["block_index"] = idx  # use as delete block id
    return blocks

def annotate_tokens_with_blocks(tokens, replacement_blocks, insert_blocks, delete_blocks, start_key, end_key):
    """
    Annotate a list of tokens with block identifiers if the token index falls within a block's range.
    
    Parameters:
      tokens: the list of tokens to annotate.
      replacement_blocks: list of replacement block dicts.
      insert_blocks: list of insert block dicts.
      delete_blocks: list of delete block dicts.
      start_key: the key for the starting index in the block dict (e.g., "final_start" or "annotated_start").
      end_key: the key for the ending index in the block dict (e.g., "final_end" or "annotated_end").
      
    Annotated keys added to tokens:
      - "replacementBlockId" from replacement_blocks (using rb["block_index"])
      - "insertBlockId" from insert_blocks (using ib["insert_block_index"] if available, else ib["block_index"])
      - "deleteBlockId" from delete_blocks (using db["delete_block_index"] if available, else db["block_index"])
    """
    for token in tokens:
        idx = token["index"]
        for rb in replacement_blocks:
            s = rb.get(start_key, rb.get("final_start"))
            e = rb.get(end_key, rb.get("final_end"))
            if idx >= s and idx <= e:
                token["replacementBlockId"] = rb["block_index"]
        for ib in insert_blocks:
            s = ib.get(start_key, ib.get("final_start"))
            e = ib.get(end_key, ib.get("final_end"))
            if idx >= s and idx <= e:
                token["insertBlockId"] = ib.get("insert_block_index", ib.get("block_index"))
        for db in delete_blocks:
            s = db.get(start_key, db.get("final_start"))
            e = db.get(end_key, db.get("final_end"))
            if idx >= s and idx <= e:
                token["deleteBlockId"] = db.get("delete_block_index", db.get("block_index"))
    return tokens

def print_sentence_debug(sentence_idx, final_sentence, replacement_ann_blocks, replacement_fin_blocks, annotated_line):
    """
    Debug printing for replacement blocks and insert/delete blocks.
    """
    print(f"\n=== Sentence {sentence_idx + 1} ===")
    print("Final Sentence Tokens:")
    for i, tok in enumerate(final_sentence):
        print(f"  {i}: char='{tok['char']}', type='{tok['type']}'")
    print("\nAnnotated Tokens:")
    for i, tok in enumerate(annotated_line):
        print(f"  {i}: char='{tok['char']}', type='{tok['type']}'")
    
    corrected_map = {}
    for b in replacement_ann_blocks:
        c_text = "".join(t["char"] for t in b["tokens"])
        corrected_map[b["block_index"]] = {"start": b["start"], "end": b["end"], "text": c_text}
    replaced_map = {}
    for b in replacement_fin_blocks:
        r_text = "".join(t["char"] for t in b["tokens"])
        replaced_map[b["block_index"]] = {"start": b["start"], "end": b["end"], "text": r_text}
    
    all_block_ids = sorted(set(corrected_map.keys()) | set(replaced_map.keys()))
    print("Blocks:")
    for bidx in all_block_ids:
        c_info = corrected_map.get(bidx, {})
        r_info = replaced_map.get(bidx, {})
        print(f"  replacement_block {bidx}:")
        print(f"    corrected='{c_info.get('text', '')}' (start={c_info.get('start')}, end={c_info.get('end')})")
        print(f"    replaced ='{r_info.get('text', '')}' (start={r_info.get('start')}, end={r_info.get('end')})")
    
    print("\nInsert Blocks:")
    for blk in detect_insert_blocks(final_sentence):
        print(f"  insert_block_index={blk.get('insert_block_index', blk.get('block_index'))}, start={blk['start']}, end={blk['end']}, text='{''.join(tok['char'] for tok in blk['tokens'])}'")
    
    print("\nDelete Blocks:")
    for blk in detect_delete_blocks(final_sentence):
        print(f"  delete_block_index={blk.get('delete_block_index', blk.get('block_index'))}, start={blk['start']}, end={blk['end']}, text='{''.join(tok['char'] for tok in blk['tokens'])}'")

def extend_final_tokens(final_tokens, up_to_index):
    """
    Pad the final tokens up to `up_to_index` if needed,
    using placeholders (type 'equal', char=' ').
    """
    if not final_tokens:
        return final_tokens
    last_idx = final_tokens[-1]["index"]
    if up_to_index > last_idx:
        for idx in range(last_idx + 1, up_to_index + 1):
            final_tokens.append({"index": idx, "char": " ", "type": "equal"})
    return final_tokens

def prepare_json_output(replacement_ann_blocks_all, replacement_fin_blocks_all, insert_blocks_all, delete_blocks_all, final_sentences, annotated_lines, sentence_entries=None):
    """
    Return final JSON structure with container_length and embed block metadata directly
    into both the final sentence tokens and the annotated tokens.
    """
    sentences_data = []
    for sentence_index in range(len(final_sentences)):
        final_sentence = final_sentences[sentence_index]
        ann_line = annotated_lines[sentence_index]
        sentence_entry = sentence_entries[sentence_index] if sentence_entries and sentence_index < len(sentence_entries) else {}
        
        # Replacement blocks for this sentence
        ann_blocks = replacement_ann_blocks_all[sentence_index]
        fin_blocks = replacement_fin_blocks_all[sentence_index]
        # Insert and delete blocks for this sentence
        ins_blocks = insert_blocks_all[sentence_index]
        del_blocks = delete_blocks_all[sentence_index]
        
        if ann_blocks:
            max_anno_end = max(b["end"] for b in ann_blocks)
            final_sentence = extend_final_tokens(final_sentence, max_anno_end)
        
        container_len = compute_container_length(ann_line, final_sentence)
        
        # Build replacement_blocks array for output
        replacement_blocks = []
        for ann_block, fin_block in zip(ann_blocks, fin_blocks):
            replaced_text = "".join(tok["char"] for tok in fin_block["tokens"])
            corrected_text = "".join(tok["char"] for tok in ann_block["tokens"])
            replacement_blocks.append({
                "block_index": ann_block["block_index"],
                "final_start": fin_block["start"],
                "final_end": fin_block["end"],
                "replaced_text": replaced_text,
                "annotated_start": ann_block["start"],
                "annotated_end": ann_block["end"],
                "corrected_text": corrected_text
            })
        
        # Build insert_blocks array for output
        insert_blocks = []
        for blk in ins_blocks:
            text = "".join(tok["char"] for tok in blk["tokens"])
            insert_blocks.append({
                "insert_block_index": blk["block_index"],
                "final_start": blk["start"],
                "final_end": blk["end"],
                "insert_text": text
            })
        
        # Build delete_blocks array for output
        delete_blocks = []
        for blk in del_blocks:
            text = "".join(tok["char"] for tok in blk["tokens"])
            delete_blocks.append({
                "delete_block_index": blk["block_index"],
                "final_start": blk["start"],
                "final_end": blk["end"],
                "delete_text": text
            })
        
        # Annotate final tokens using final boundaries
        final_sentence = annotate_tokens_with_blocks(final_sentence,
                                                       replacement_blocks,
                                                       insert_blocks,
                                                       delete_blocks,
                                                       start_key="final_start",
                                                       end_key="final_end")
        
        # Annotate annotated tokens using annotated boundaries.
        # For insert and delete blocks, if "annotated_start" is not present, fall back to final boundaries.
        annotated_tokens = annotate_tokens_with_blocks(ann_line,
                                                         replacement_blocks,
                                                         insert_blocks,
                                                         delete_blocks,
                                                         start_key="annotated_start",
                                                         end_key="annotated_end")
        
        sentences_data.append({
            "sentence_index": sentence_entry.get("sentence_index", sentence_index),
            "render_mode": "token_diff",
            "source_sentence_index": sentence_entry.get("source_sentence_index"),
            "correction_mode": sentence_entry.get("correction_mode"),
            "is_combined_scope": bool(sentence_entry.get("is_combined_scope", False)),
            "combined_scope_side": sentence_entry.get("combined_scope_side"),
            "final_sentence_tokens": final_sentence,
            "annotated_tokens": annotated_tokens,
            "replacement_blocks": replacement_blocks,
            "insert_blocks": insert_blocks,
            "delete_blocks": delete_blocks,
            "container_length": container_len
        })

    return {"sentences": sentences_data}


def build_aligned_text_sentence(mapping_entry):
    ocr_text = _normalize_sentence_text(mapping_entry.get("ocr_sentence", ""))
    corrected_text = _normalize_sentence_text(mapping_entry.get("corrected_sentence", ""))
    return {
        "sentence_index": mapping_entry.get("sentence_index", 0),
        "render_mode": "aligned_text",
        "ocr_text": ocr_text,
        "corrected_text": corrected_text,
        "container_length": max(len(ocr_text), len(corrected_text), 20)
    }


def merge_render_payload(sentence_mapping, token_diff_output):
    token_diff_by_index = {
        sentence.get("sentence_index"): sentence
        for sentence in token_diff_output.get("sentences", [])
    }
    merged_sentences = []
    for mapping_entry in sentence_mapping.get("sentences", []):
        sentence_index = mapping_entry.get("sentence_index")
        if mapping_entry.get("render_mode") == "aligned_text":
            merged_sentences.append(build_aligned_text_sentence(mapping_entry))
            continue
        token_diff_sentence = token_diff_by_index.get(sentence_index)
        if token_diff_sentence is not None:
            merged_sentences.append(token_diff_sentence)
    return {"sentences": merged_sentences}

if __name__ == "__main__":
    with open("final_output.pkl", "rb") as f:
        data = pickle.load(f)
        annotated_lines = data["annotated_lines"]
        final_sentences = data["final_sentences"]
    
    annotated_lines = [replace_double_quotes_in_tokens(line) for line in annotated_lines]
    final_sentences = [replace_double_quotes_in_tokens(sentence) for sentence in final_sentences]
    
    for sentence in final_sentences:
        for i, token in enumerate(sentence):
            token["index"] = i
    for ann_line in annotated_lines:
        for i, token in enumerate(ann_line):
            token["index"] = i
    
    replacement_ann_blocks_all = []
    replacement_fin_blocks_all = []
    for ann_line, fin_line in zip(annotated_lines, final_sentences):
        ann_blocks, fin_blocks = detect_replacement_blocks(ann_line, fin_line)
        replacement_ann_blocks_all.append(ann_blocks)
        replacement_fin_blocks_all.append(fin_blocks)
    
    insert_blocks_all = []
    delete_blocks_all = []
    for fin_line in final_sentences:
        ins_blks = detect_insert_blocks(fin_line)
        del_blks = detect_delete_blocks(fin_line)
        insert_blocks_all.append(ins_blks)
        delete_blocks_all.append(del_blks)
    
    for idx, (ann_blocks, fin_blocks, final_line, annotated_line) in enumerate(
            zip(replacement_ann_blocks_all, replacement_fin_blocks_all, final_sentences, annotated_lines)):
        print_sentence_debug(idx, final_line, ann_blocks, fin_blocks, annotated_line)
    
    output_data = prepare_json_output(
        replacement_ann_blocks_all,
        replacement_fin_blocks_all,
        insert_blocks_all,
        delete_blocks_all,
        final_sentences,
        annotated_lines
    )
    
    with open("output.json", "w") as f:
        json.dump(output_data, f, indent=4)
    
    print("\n[INFO] Wrote output.json successfully")
