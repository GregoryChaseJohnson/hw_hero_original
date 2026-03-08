import re
from fuzzywuzzy import fuzz
import json



def split_into_sentences(raw_text):
    """
    Split text into sentences while handling edge cases,
    such as abbreviations (e.g., 'etc.', 'e.g.') and periods followed by commas (e.g., 'etc.,').
    """
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', raw_text)
    text = re.sub(r'\b(etc)\.', r'\1<PROTECTEDPERIOD>', text) 

    # List of common abbreviations that should not end sentences
    abbreviations = r'\b(?:etc|e\.g|i\.e|vs|Dr|Mr|Mrs|Ms|Prof|Jr|Sr)\.'

    # Protect abbreviations and edge cases by temporarily replacing periods
    text = re.sub(fr'({abbreviations})', r'\1<PERIOD>', text)
    text = re.sub(r'\.\,', '<DOTCOMMA>', text)

    # Regex to split sentences directly
    sentences = re.split(r'([.!?]["\']?\s+)', text)  # Match punctuation + quotes + space

    # Combine the sentences properly
    combined_sentences = []
    buffer = ""
    for segment in sentences:
        if re.match(r'[.!?]["\']?\s+', segment):
            buffer += segment  # Append the punctuation to the previous buffer
            combined_sentences.append(buffer.strip())
            buffer = ""
        else:
            buffer += segment  # Accumulate sentence text

    # Add any remaining text as a sentence
    if buffer.strip():
        combined_sentences.append(buffer.strip())

    # Restore protected periods and commas
    combined_sentences = [
        re.sub(r'(<PERIOD>)+', '.', s).replace('<DOTCOMMA>', '.,').replace('<PROTECTEDPERIOD>', '.') 
        for s in combined_sentences
    ]

    return combined_sentences

def find_best_matches_bidirectional(ocr_sentences, corrected_sentences, min_score=70):
    """
    Match OCR sentences to corrected sentences, handling splits and merges bidirectionally.
    """
    matches = []
    corrected_index = 0  # Track the current corrected sentence index
    skip_next_ocr = False  # Flag to skip the next OCR sentence if combined
    skip_next_corrected = False  # Flag to skip the next corrected sentence if combined

    for i, ocr_sentence in enumerate(ocr_sentences):
        if skip_next_ocr:
            skip_next_ocr = False
            continue

        if corrected_index >= len(corrected_sentences):
            # If no more corrected sentences, append unmatched
            matches.append((ocr_sentence, "NO GOOD MATCH"))
            continue

        # Initialize variables
        current_corrected = corrected_sentences[corrected_index]
        score_current = fuzz.ratio(ocr_sentence, current_corrected)
        best_match = (current_corrected, score_current)

        # Lookahead: Combine corrected sentences
        score_next, combined_corrected = 0, ""
        if corrected_index + 1 < len(corrected_sentences):
            next_corrected = corrected_sentences[corrected_index + 1]
            score_next = fuzz.ratio(ocr_sentence, next_corrected)
            combined_corrected = current_corrected + " " + next_corrected
            score_combined_corrected = fuzz.ratio(ocr_sentence, combined_corrected)
        else:
            score_combined_corrected = 0

        # Lookahead: Combine OCR sentences
        combined_ocr = ""
        if i + 1 < len(ocr_sentences):
            next_ocr = ocr_sentences[i + 1]
            combined_ocr = ocr_sentence + " " + next_ocr
            score_combined_ocr = fuzz.ratio(combined_ocr, current_corrected)
        else:
            score_combined_ocr = 0

        # Determine the best match
        if score_current >= min_score and score_current >= score_next and score_current >= max(score_combined_corrected, score_combined_ocr):
            best_match = (current_corrected, score_current)
            corrected_index += 1  # Advance to the next corrected sentence
        elif score_next >= min_score and score_next >= score_combined_corrected and score_next >= score_combined_ocr:
            best_match = (next_corrected, score_next)
            corrected_index += 2  # Skip to the sentence after the next
        elif score_combined_corrected >= min_score and score_combined_corrected >= score_combined_ocr:
            best_match = (combined_corrected, score_combined_corrected)
            corrected_index += 2  # Skip the combined corrected sentences
            skip_next_corrected = True
        elif score_combined_ocr >= min_score:
            best_match = (current_corrected, score_combined_ocr)
            skip_next_ocr = True  # Skip the next OCR sentence as it's combined
            corrected_index += 1

        # Append the match
        matches.append((ocr_sentence, best_match[0]))

    return matches

with open("/home/keithuncouth/red_pen_app/renderer/tests/ocr_output.json", "r") as f:
    ocr_data = json.load(f)
with open("/home/keithuncouth/red_pen_app/renderer/tests/corrected_text.json", "r") as f:
    corrected_data = json.load(f)

ocr_text = ocr_data["ocr_text"]
corrected_text = corrected_data["corrected_text"]

# Step 1: Split both texts into sentences
ocr_sentences = split_into_sentences(ocr_text)
corrected_sentences = split_into_sentences(corrected_text)

# Step 2: Perform matching with rules
# Step 2: Perform matching with rules
matches = find_best_matches_bidirectional(ocr_sentences, corrected_sentences)

for match in matches:
    print(match)  # Print each tuple for clarity

# Step 3: Save sentence pairs to JSON
with open("/home/keithuncouth/red_pen_app/renderer/tests/sentence_pairs.json", "w", encoding="utf-8") as f:
    json.dump(matches, f, ensure_ascii=False, indent=4)

print("Sentence pairs have been saved to 'sentence_pairs.json'.")


# Step 3: Output sentence pairs
for ocr_sentence, best_match in matches:
    print(f"Original: {ocr_sentence}")
    print(f"Corrected: {best_match}")
    print("-" * 40)
