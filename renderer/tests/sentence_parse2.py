import re
import difflib
import json
from typing import List, Tuple

def split_into_sentences(text: str) -> List[str]:
    """
    Split text into sentences, ensuring proper handling of sentence-ending punctuation.
    """
    # Protect abbreviations and other non-sentence-ending periods
    abbreviations = r'\b(?:etc|e\.g|i\.e|vs|Dr|Mr|Mrs|Ms|Prof|Jr|Sr)\.'
    text = re.sub(fr'({abbreviations})', r'\1<PROTECTED>', text)

    # Use sentence-ending punctuation to split sentences
    sentence_endings = r'([.!?]["\')\]]?\s+)'  # Matches punctuation with optional quotes
    tokens = re.split(sentence_endings, text)

    # Combine tokens into sentences
    sentences = []
    buffer = ""
    for token in tokens:
        buffer += token
        if re.search(sentence_endings, token):  # If this is the end of a sentence, finalize it
            sentences.append(buffer.strip())
            buffer = ""
    if buffer.strip():  # Add any remaining text
        sentences.append(buffer.strip())

    # Restore protected abbreviations
    sentences = [re.sub(r'\.<PROTECTED>', '.', s) for s in sentences]  # Fix duplicated periods
    sentences = [s.replace('<PROTECTED>', '.') for s in sentences]  # Ensure complete restoration

    return sentences

def tokenize(text: str) -> List[str]:
    """
    Tokenize text into words, spaces, and punctuation separately.
    """
    return re.findall(r'\w+|\s+|[^\w\s]', text)

def get_sentence_diffs(original: str, corrected: str) -> List[Tuple[int, str, str]]:
    """
    Identify differences between original and corrected texts by sentence.
    """
    original_sentences = split_into_sentences(original)
    corrected_sentences = split_into_sentences(corrected)

    sm = difflib.SequenceMatcher(None, original_sentences, corrected_sentences)
    diffs = []
    num = 1
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            num += i2 - i1
        elif tag in ('replace', 'delete', 'insert'):
            max_range = max(i2 - i1, j2 - j1)
            for idx in range(max_range):
                o_sent = original_sentences[i1 + idx] if i1 + idx < i2 else ''
                c_sent = corrected_sentences[j1 + idx] if j1 + idx < j2 else ''
                diffs.append((num, o_sent, c_sent))
                num += 1
    return diffs

def align_and_highlight(original: List[str], corrected: List[str]) -> str:
    """
    Align tokens between original and corrected sentences and highlight changes.
    """
    sm = difflib.SequenceMatcher(None, original, corrected)
    highlighted = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            highlighted.extend(corrected[j1:j2])
        elif tag == 'replace':
            highlighted.extend(f"\033[91m{token}\033[0m" for token in original[i1:i2])  # Red for deletions
            highlighted.extend(f"\033[92m{token}\033[0m" for token in corrected[j1:j2])  # Green for additions
        elif tag == 'delete':
            highlighted.extend(f"\033[95;1m{token}\033[0m" for token in original[i1:i2])
        elif tag == 'insert':
            highlighted.extend(f"\033[94m{token}\033[0m" for token in corrected[j1:j2])
    return ''.join(highlighted)

def highlight_changes(original: str, corrected: str) -> str:
    """
    Tokenize sentences and highlight changes using structured alignment.
    """
    if not original:
        return f"\033[94m{corrected}\033[0m"  # Blue for additions
    elif not corrected:
        return f"\033[93m{original}\033[0m"  # Yellow for deletions
    else:
        orig_tokens = tokenize(original)
        corr_tokens = tokenize(corrected)
        return align_and_highlight(orig_tokens, wcorr_tokens)

def generate_report(original: str, corrected: str) -> str:
    """
    Generate a report of changes with sentence numbers and color formatting.
    """
    diffs = get_sentence_diffs(original, corrected)
    report = []
    for num, orig, corr in diffs:
        highlighted = highlight_changes(orig, corr)
        report.append(highlighted)
    return "\n\n".join(report)

# Load sentence pairs from JSON
with open("sentence_pairs.json", "r", encoding="utf-8") as f:
    sentence_pairs = json.load(f)

fused_differences = []

# Print only the fused differences for each sentence pair with separators
for original, corrected in sentence_pairs:
    fused_difference = highlight_changes(original, corrected)
    fused_differences.append(fused_difference)  # Add to list
    print(fused_difference)
    print("-" * 40)  # Separator line

# Save fused differences to JSON
with open("fused_differences.json", "w", encoding="utf-8") as f:
    json.dump(fused_differences, f, ensure_ascii=False, indent=4)

print("Fused differences saved to 'fused_differences.json'.")