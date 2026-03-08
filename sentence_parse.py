import re
import difflib
from typing import List, Tuple

def split_into_sentences(text: str) -> List[str]:
    """
    Split text into sentences, including sentence-ending punctuation.
    This avoids the use of variable-length look-behinds.
    """
    sentence_endings = r'([.!?]["\')\]]?\s+)'
    tokens = re.split(sentence_endings, text)
    sentences = []
    i = 0
    while i < len(tokens):
        if i + 1 < len(tokens):
            # Combine the sentence with its ending punctuation and whitespace
            sentence = tokens[i] + tokens[i+1]
            i += 2
        else:
            # Add any remaining text as a sentence
            sentence = tokens[i]
            i += 1
        sentences.append(sentence.strip())
    return sentences

def tokenize(text: str) -> List[str]:
    """Tokenize text into words, spaces, and punctuation separately."""
    return re.findall(r'\w+|\s+|[^\w\s]', text)

def get_sentence_diffs(original: str, corrected: str) -> List[Tuple[int, str, str]]:
    """
    Identify differences between original and corrected texts by sentence,
    handling misalignments due to additions or deletions.
    """
    original_sentences = split_into_sentences(original)
    corrected_sentences = split_into_sentences(corrected)

    sm = difflib.SequenceMatcher(None, original_sentences, corrected_sentences)
    diffs = []
    num = 1  # Sentence numbering
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            num += i2 - i1  # Advance sentence numbering
        elif tag in ('replace', 'delete', 'insert'):
            # Handle replacements, deletions, and insertions
            max_range = max(i2 - i1, j2 - j1)
            for idx in range(max_range):
                o_sent = original_sentences[i1 + idx] if i1 + idx < i2 else ''
                c_sent = corrected_sentences[j1 + idx] if j1 + idx < j2 else ''
                diffs.append((num, o_sent, c_sent))
                num += 1
    return diffs

def align_and_highlight(original: List[str], corrected: List[str]) -> str:
    """Align tokens between original and corrected sentences and highlight changes."""
    sm = difflib.SequenceMatcher(None, original, corrected)
    highlighted = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            highlighted.extend(corrected[j1:j2])
        elif tag == 'replace':
            # Highlight deletions in red and additions in green
            highlighted.extend(f"\033[91m{token}\033[0m" for token in original[i1:i2])
            highlighted.extend(f"\033[92m{token}\033[0m" for token in corrected[j1:j2])
        elif tag == 'delete':
            highlighted.extend(f"\033[91m{token}\033[0m" for token in original[i1:i2])
        elif tag == 'insert':
            highlighted.extend(f"\033[92m{token}\033[0m" for token in corrected[j1:j2])
    return ''.join(highlighted)

def highlight_changes(original: str, corrected: str) -> str:
    """Tokenize sentences and highlight changes using structured alignment."""
    if not original:
        # Entirely new sentence added
        return f"\033[92m{corrected}\033[0m"  # Green for additions
    elif not corrected:
        # Entire sentence deleted
        return f"\033[91m{original}\033[0m"  # Red for deletions
    else:
        orig_tokens = tokenize(original)
        corr_tokens = tokenize(corrected)
        return align_and_highlight(orig_tokens, corr_tokens)

def generate_report(original: str, corrected: str) -> str:
    """Generate a report of changes with sentence numbers and color formatting."""
    diffs = get_sentence_diffs(original, corrected)
    report = []
    for num, orig, corr in diffs:
        highlighted = highlight_changes(orig, corr)
        report.append(f"Sentence {num}: {highlighted}")
    return "\n\n".join(report)

# Example usage:
original_text = (

    "The day I just spent my free, time for having a branch at the cafe and walking around the town in the city." 
)

corrected_text = (
    "During the day, I spent my free time having brunch at a café and walking around the town."
)

report = generate_report(original_text, corrected_text)
print(report)
