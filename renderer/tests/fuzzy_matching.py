import re
from fuzzywuzzy import fuzz

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

def find_best_matches_with_rules(ocr_sentences, corrected_sentences, min_score=70):
    """
    Sequentially match OCR sentences to corrected sentences with rules for handling splits and merges.
    """
    matches = []
    corrected_index = 0  # Track the current corrected sentence index

    for ocr_sentence in ocr_sentences:
        if corrected_index >= len(corrected_sentences):
            # If no more corrected sentences, append unmatched
            matches.append((ocr_sentence, "NO GOOD MATCH"))
            continue

        # Current corrected sentence
        current_corrected = corrected_sentences[corrected_index]

        # Compare with current sentence
        score_current = fuzz.ratio(ocr_sentence, current_corrected)

        # Lookahead: Compare with the next sentence (if it exists)
        score_next = 0
        combined_next = ""
        if corrected_index + 1 < len(corrected_sentences):
            next_corrected = corrected_sentences[corrected_index + 1]
            score_next = fuzz.ratio(ocr_sentence, next_corrected)
            # Combine current and next corrected sentences
            combined_next = current_corrected + " " + next_corrected
            score_combined = fuzz.ratio(ocr_sentence, combined_next)
        else:
            score_combined = 0

        # Choose the best match based on scores
        if score_current >= min_score and score_current >= score_next and score_current >= score_combined:
            # Match with the current corrected sentence
            matches.append((ocr_sentence, current_corrected))
            corrected_index += 1
        elif score_next >= min_score and score_next >= score_combined:
            # Match with the next corrected sentence
            matches.append((ocr_sentence, next_corrected))
            corrected_index += 2  # Skip to the sentence after the next
        elif score_combined >= min_score:
            # Match with the combined sentences
            matches.append((ocr_sentence, combined_next))
            corrected_index += 2  # Skip to the sentence after the next
        else:
            # No good match
            matches.append((ocr_sentence, "NO GOOD MATCH"))
            corrected_index += 1

    return matches

# Example OCR output
ocr_text = """Personal Perspective Essay

PE subjects are mandatory in Korean schools. Therefore, students are supposed to join the PE class whether they want to or not. Although physical activities are beneficial for some students, some students might think it is a waste of time and energy. Is it really right to force students to join PE classes?

I believe that sport classes should be optional in schools. I have two personal experiences that support my thought.

First of all, sports have a high risk of injuries. In other terms, sports are not safe. When I was in the 4th grade, my friend hurt her back while doing an activity called "twimtaulthigi." She needed to jump over a stack of blocks called "twimtaul," but she was not a sport person, she fell on her back and got seriously injured. She couldn't come to school for the next three days. Is it right for schools to force students to do something not safe? I don't think so.

Also, sports are not suitable for everyone. Of course, some students enjoy sports. But some students do not like sports and do not participate in the game well. Some lie to the teacher that they do not feel well, and others just stand in the middle of the game doing nothing. My best

"""

# Corrected text
corrected_text = """Personal Perspective Essay

PE subjects are mandatory in Korean schools. Therefore, students are supposed to join the PE class whether they want to or not. Although physical activities are beneficial for some students, others might think it is a waste of time and energy. Is it really right to force students to join PE classes?

I believe that sports classes should be optional in schools. I have two personal experiences that support my opinion.

First of all, sports have a high risk of injuries. In other words, sports are not safe. When I was in the 4th grade, my friend hurt her back while doing an activity called "twimtaulthigi." She needed to jump over a stack of blocks called "twimtaul," but since she was not a sporty person, she fell on her back and got seriously injured. She couldn't come to school for the next three days. Is it right for schools to force students to do something that is not safe? I don't think so.

Also, sports are not suitable for everyone. Of course, some students enjoy sports, but others do not like them and do not participate well in the games. Some lie to the teacher that they do not feel well, while others just stand in the middle of the game doing nothing. My best friend...



"""

# Step 1: Split both texts into sentences
ocr_sentences = split_into_sentences(ocr_text)
corrected_sentences = split_into_sentences(corrected_text)

# Step 2: Perform matching with rules
matches = find_best_matches_with_rules(ocr_sentences, corrected_sentences)

# Step 3: Output sentence pairs
for ocr_sentence, best_match in matches:
    print(f"Original: {ocr_sentence}")
    print(f"Corrected: {best_match}")
    print("-" * 40)
