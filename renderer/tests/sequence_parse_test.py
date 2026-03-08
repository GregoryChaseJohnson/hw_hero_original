import re
from fuzzywuzzy import fuzz
import difflib
from typing import List, Tuple

# Importing functions from `sequence_aligner.py`
def split_into_sentences(raw_text):
    # Normalize whitespace and handle abbreviations
    text = re.sub(r'\s+', ' ', raw_text)
    text = re.sub(r'\b(etc)\.', r'\1<PROTECTEDPERIOD>', text)
    abbreviations = r'\b(?:etc|e\.g|i\.e|vs|Dr|Mr|Mrs|Ms|Prof|Jr|Sr)\.'
    text = re.sub(fr'({abbreviations})', r'\1<PERIOD>', text)
    text = re.sub(r'\.\,', '<DOTCOMMA>', text)
    sentences = re.split(r'([.!?]["\']?\s+)', text)
    combined_sentences = []
    buffer = ""
    for segment in sentences:
        if re.match(r'[.!?]["\']?\s+', segment):
            buffer += segment
            combined_sentences.append(buffer.strip())
            buffer = ""
        else:
            buffer += segment
    if buffer.strip():
        combined_sentences.append(buffer.strip())
    combined_sentences = [
        re.sub(r'(<PERIOD>)+', '.', s).replace('<DOTCOMMA>', '.,').replace('<PROTECTEDPERIOD>', '.')
        for s in combined_sentences
    ]
    return combined_sentences

def find_best_matches_bidirectional(ocr_sentences, corrected_sentences, min_score=70):
    matches = []
    corrected_index = 0
    skip_next_ocr = False
    for i, ocr_sentence in enumerate(ocr_sentences):
        if skip_next_ocr:
            skip_next_ocr = False
            continue
        if corrected_index >= len(corrected_sentences):
            matches.append((ocr_sentence, "NO GOOD MATCH"))
            continue
        current_corrected = corrected_sentences[corrected_index]
        score_current = fuzz.ratio(ocr_sentence, current_corrected)
        best_match = (current_corrected, score_current)
        score_combined_corrected = score_combined_ocr = 0
        if corrected_index + 1 < len(corrected_sentences):
            next_corrected = corrected_sentences[corrected_index + 1]
            combined_corrected = current_corrected + " " + next_corrected
            score_combined_corrected = fuzz.ratio(ocr_sentence, combined_corrected)
        if i + 1 < len(ocr_sentences):
            next_ocr = ocr_sentences[i + 1]
            combined_ocr = ocr_sentence + " " + next_ocr
            score_combined_ocr = fuzz.ratio(combined_ocr, current_corrected)
        if score_current >= min_score and score_current >= max(score_combined_corrected, score_combined_ocr):
            corrected_index += 1
        elif score_combined_corrected >= min_score:
            best_match = (combined_corrected, score_combined_corrected)
            corrected_index += 2
        elif score_combined_ocr >= min_score:
            skip_next_ocr = True
            corrected_index += 1
        matches.append((ocr_sentence, best_match[0]))
    return matches

# Importing functions from `sentence_parse.py`
def tokenize(text: str) -> List[str]:
    return re.findall(r'\w+|\s+|[^\w\s]', text)

def align_and_highlight(original: List[str], corrected: List[str]) -> str:
    sm = difflib.SequenceMatcher(None, original, corrected)
    highlighted = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            highlighted.extend(corrected[j1:j2])
        elif tag == 'replace':
            highlighted.extend(f"\033[91m{token}\033[0m" for token in original[i1:i2])
            highlighted.extend(f"\033[92m{token}\033[0m" for token in corrected[j1:j2])
        elif tag == 'delete':
            highlighted.extend(f"\033[93m{token}\033[0m" for token in original[i1:i2])
        elif tag == 'insert':
            highlighted.extend(f"\033[94m{token}\033[0m" for token in corrected[j1:j2])
    return ''.join(highlighted)

def highlight_changes(original: str, corrected: str) -> str:
    orig_tokens = tokenize(original)
    corr_tokens = tokenize(corrected)
    return align_and_highlight(orig_tokens, corr_tokens)

# Example usage with OCR and corrected text
ocr_text = """Recently, there are many music and K-pop singer coming out. Also, many people including youth are enjoying and affected by it. As the world keeps affected by K-pop, some people are concerned about K-pop music's bad influence because it can have the bad effect. But, for my opinion, I strongly believe that K-pop has more positive effect than harm on the youth.

Firstly, it can inspire confidence and hope. In my life, I'm having hard time due to the homework and school test. But, I sometimes get rested by hearing K-pop music and getting hope by it. Also, during COVID-19 pandemic, I was having hard time by its regulation. But when BTS's song named 'Permission to Dance', I can feel the hope to end the pandemic.

Secondly, it can make the whole culture more interest to youths. In my school, how many girl classmates gather and hang out to talk about their favorite K-pop singer or songs. Also, they collect their money or go to other place merchandise product of singer. This can trigger youths to make more friends and making them to be more socialized, which is important to later on the work.

Third and lastly, it can make Korean youth to think again about their traditional culture and proud of. Like recent I heard many about the fusion.
"""
corrected_text = """Recently, there are many music and K-pop singers coming out. Also, many people, including youth, are enjoying it and being affected by it. As the world keeps being affected by K-pop, some people are concerned about its bad influence because it can have negative effects. But in my opinion, I strongly believe that K-pop has more positive effects than harm on the youth.

Firstly, it can inspire confidence and hope. In my life, I'm having a hard time due to homework and school tests. But I sometimes get a break by listening to K-pop music and finding hope in it. Also, during the COVID-19 pandemic, I was having a tough time with the restrictions. But when I heard BTS's song "Permission to Dance," I felt hopeful about the end of the pandemic.

Secondly, it can make the whole culture more interesting to youth. In my school, many of my girl classmates gather and hang out to talk about their favorite K-pop singers or songs. They also save their money or go to other places to buy merchandise from their favorite artists. This can encourage youth to make more friends and become more social, which is important for their future work.

Third and lastly, it can make Korean youth think again about their traditional culture and feel proud of it. Like recently, I heard a lot about the fusion.
"""

# Step 1: Split sentences
ocr_sentences = split_into_sentences(ocr_text)
corrected_sentences = split_into_sentences(corrected_text)

# Step 2: Match sentences
matches = find_best_matches_bidirectional(ocr_sentences, corrected_sentences)

# Step 3: Feed matches one by one to `sentence_parse` and highlight differences
for ocr_sentence, corrected_sentence in matches:
    highlighted_output = highlight_changes(ocr_sentence, corrected_sentence)
    print(f"Original: {ocr_sentence}")
    print(f"Corrected: {corrected_sentence}")
    print(f"Highlight:\n{highlighted_output}")
    print("-" * 40)
