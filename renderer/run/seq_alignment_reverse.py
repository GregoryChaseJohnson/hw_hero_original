import re
import json
from fuzzywuzzy import fuzz

def number_ocr_sentences(ocr_sentences):
    """
    Assigns a numerical index to each OCR sentence.
    """
    return [(index, sentence) for index, sentence in enumerate(ocr_sentences)]

# Define a unique marker to indicate sentence combinations
COMBINATION_MARKER = "^**^"

def split_into_sentences(raw_text):
    def normalize_apostrophes(text):
        return (text.replace('‘', "'")
                    .replace('’', "'")
                    .replace('‛', "'")
                    .replace('`', "'")
                    .replace('´', "'"))
    
    def normalize_quotes(text):
        # Convert curly double quotes to straight double quotes
        text = text.replace('“', '"').replace('”', '"')
        # Convert single quotes to double quotes for consistency
        text = text.replace("'", '"')
        return text

    text = normalize_apostrophes(raw_text)
    text = normalize_quotes(text)
    text = re.sub(r'\s+', ' ', text)
    abbreviations = r'\b(?:etc|e\.g|i\.e|vs|Dr|Mr|Mrs|Ms|Prof|Jr|Sr|P\.E)'
    # Replace only the trailing period, not within the abbreviation
    text = re.sub(fr'({abbreviations})\.', r'\1<PERIOD>', text)
    # Preprocessing "P.E." if followed by capital letter
    text = re.sub(r'(P\.E<PERIOD>)\s+(?=[A-Z])', r'\1\n', text)
    sentence_split_pattern = r'(?<=[.!?])["\'“”‘’]?\s+(?=[A-Z])'
    text = text.replace('\n', '. ')
    sentences = re.split(sentence_split_pattern, text)
    # Restore <PERIOD> to '.'
    sentences = [s.replace('<PERIOD>', '.').strip() for s in sentences]
    cleaned_sentences = []
    for s in sentences:
        # Replace multiple consecutive periods with a single period
        s = re.sub(r'\.(\s*\.)+', '.', s)
        cleaned_sentences.append(s)
    return cleaned_sentences

def insert_marker_in_combination(first_sentence, marker=COMBINATION_MARKER):
    """
    Append the marker directly to the end of the first sentence.
    """
    return first_sentence.strip() + marker

def find_best_matches_simplified(ocr_sentences, corrected_sentences, min_score=50):
    """
    Matches OCR sentences with corrected sentences using simplified logic:
    1. Single OCR sentence vs single corrected sentence.
    2. Single OCR sentence vs two corrected sentences combined.
    3. Two OCR sentences combined vs single corrected sentence.
    """
    matches = []
    ocr_index = 0
    corrected_index = 0

    while ocr_index < len(ocr_sentences) and corrected_index < len(corrected_sentences):
        ocr_sentence = ocr_sentences[ocr_index]
        corrected_sentence = corrected_sentences[corrected_index]
        
        # Compare single vs single
        score_single = fuzz.ratio(ocr_sentence, corrected_sentence)
        best_score = score_single
        best_match = (ocr_sentence, corrected_sentence)
        increment_ocr = 1
        increment_corrected = 1

        # Compare single OCR vs two corrected combined
        if corrected_index + 1 < len(corrected_sentences):
            corrected_combined = corrected_sentence + " " + corrected_sentences[corrected_index + 1]
            score_combined_corrected = fuzz.ratio(ocr_sentence, corrected_combined)
            if score_combined_corrected > best_score and score_combined_corrected >= min_score:
                best_score = score_combined_corrected
                # Insert marker in the first corrected sentence before combining
                corrected_combined = insert_marker_in_combination(corrected_sentence) + " " + corrected_sentences[corrected_index + 1]
                best_match = (ocr_sentence, corrected_combined)
                increment_corrected = 2

        # Compare two OCR combined vs single corrected
        if ocr_index + 1 < len(ocr_sentences):
            ocr_combined = ocr_sentence + " " + ocr_sentences[ocr_index + 1]
            score_combined_ocr = fuzz.ratio(ocr_combined, corrected_sentence)
            if score_combined_ocr > best_score and score_combined_ocr >= min_score:
                best_score = score_combined_ocr
                # Insert marker in the first OCR sentence before combining
                ocr_combined = insert_marker_in_combination(ocr_sentence) + " " + ocr_sentences[ocr_index + 1]
                best_match = (ocr_combined, corrected_sentence)
                increment_ocr = 2
                # Revert to single increment for corrected since two-ocr scenario is chosen
                increment_corrected = 1

        matches.append(best_match)
        ocr_index += increment_ocr
        corrected_index += increment_corrected

    # Handle remaining unmatched OCR sentences
    while ocr_index < len(ocr_sentences):
        matches.append((ocr_sentences[ocr_index], "NO MATCH"))
        ocr_index += 1

    return matches

def align_sentences(ocr_text, corrected_text):
    """
    Align OCR text with corrected text using simplified logic with combination marker.
    """
    ocr_sentences = split_into_sentences(ocr_text)
    corrected_sentences = split_into_sentences(corrected_text)
    print("Corrected Text Sentences:", corrected_sentences)
    matches = find_best_matches_simplified(ocr_sentences, corrected_sentences, min_score=50)
    return matches

# --- New Function 1: Remove Combination Marker ---
def clean_aligned_pairs(aligned_pairs, marker=COMBINATION_MARKER):
    """
    Removes the combination marker from both OCR and corrected sentences in the aligned pairs.

    Reasoning:
    - The combination marker is inserted when two sentences are merged.
    - Downstream processing requires clean sentences without markers.
    - Removing the marker ensures that JSON mapping and API calls receive clean text.

    Args:
        aligned_pairs (list[tuple[str, str]]): List of tuples (ocr_sentence, corrected_sentence).
        marker (str): The marker string to remove.

    Returns:
        list[tuple[str, str]]: Cleaned aligned pairs.
    """
    cleaned_pairs = []
    for ocr_sentence, corrected_sentence in aligned_pairs:
        cleaned_ocr = ocr_sentence.replace(marker, "").strip()
        cleaned_corrected = corrected_sentence.replace(marker, "").strip()
        cleaned_pairs.append((cleaned_ocr, cleaned_corrected))
    return cleaned_pairs

# --- New Function 2: Create Sentence Mapping ---
def create_sentence_mapping(aligned_pairs):
    """
    Creates a mapping of sentence indexes to OCR and corrected sentences.
    
    Args:
        aligned_pairs (list[tuple[str, str]]): List of tuples (ocr_sentence, corrected_sentence).
    
    Returns:
        dict: Mapping dictionary in the form:
              {
                "sentences": [
                  {"sentence_index": 0, "ocr_sentence": ..., "corrected_sentence": ...},
                  ...
                ]
              }
    """
    mapping = {"sentences": []}
    for idx, (ocr_sentence, corrected_sentence) in enumerate(aligned_pairs):
        mapping["sentences"].append({
            "sentence_index": idx,
            "ocr_sentence": ocr_sentence,
            "corrected_sentence": corrected_sentence
        })
    return mapping

if __name__ == "__main__":
    example_ocr_text = """
      What is your favorite subject in your school? If I ask this to my friends most of them says that it is P.E class. P.E class is the only time for students to exercise and play around during school time. It can be the best time for most of the students, but however, there are some students which don't want to exercise during P.E time. They don't want to move their body or have physical disadvantages. However, many schools are still requiring P.E and sports time. So, should sports should be required in school? I believe that it should be not required, but should be optional.

First, we should respect students' opinions. Some students want sports time. But some does not. We can't require even one side's opinion. In my school, we have selected-subject time. We can choose the class which I wants and we could also choose what sports class I could attend. And to respect each students our school made the board game class. And we could be able to just relax or play board games during sports time.

Second, it can make dark history to some students. If we play any sports, sometimes we make mistakes. But most of the students criticize the student which made a mistake. And some even bullies. When I was in middle school first grade, I was playing soccer with my classmates. I was playing as goalkeeper. But I made a mistake, and we lose one goal. Then, one of my classmate which is bully and said "Are you out of mind? Saving
    """
    example_corrected_text = """What is your favorite subject in school? If I ask my friends, most of them say it's P.E. P.E. class is the only time for students to exercise and have fun during school. It can be the best time for many students, but there are some who don’t want to exercise during P.E. They don’t want to move their bodies or may have physical challenges. Still, many schools require P.E. and sports time. So, should sports be required in school? I believe it shouldn’t be required but should be optional.

First, we should respect students' opinions. Some students want sports time, but some don’t. We can’t force one side’s opinion. In my school, we have selected-subject time. We can choose the classes we want, including which sports class to attend. To respect all students, our school even created a board game class, so we can relax or play board games during sports time.

Second, sports can bring up bad memories for some students. When we play sports, we sometimes make mistakes. But many students criticize those who mess up, and some even bully them. When I was in first grade in middle school, I was playing soccer with my classmates. I was the goalkeeper, but I made a mistake and we let in a goal. Then, one of my classmates, who was a bully, said, "Are you out of your mind? Saving...
"""

    # Get aligned pairs from the alignment function
    aligned_pairs = align_sentences(example_ocr_text, example_corrected_text)
    
    # Clean the aligned pairs by removing any combination markers
    cleaned_pairs = clean_aligned_pairs(aligned_pairs)
    
    # Create sentence mapping from the cleaned pairs
    sentence_mapping = create_sentence_mapping(cleaned_pairs)
    
    # Optionally, save the mapping to a JSON file
    json_output_path = "sentence_mapping.json"
    with open(json_output_path, "w", encoding="utf-8") as f:
        json.dump(sentence_mapping, f, indent=4, ensure_ascii=False)
    
    print(f"Sentence mapping saved to {json_output_path}")
    
    # Debug: Print mapped sentences
    for entry in sentence_mapping["sentences"]:
        print(f"Index: {entry['sentence_index']}, OCR: {entry['ocr_sentence']}, Corrected: {entry['corrected_sentence']}")
    
    # Also, print the listed OCR sentences for reference
    split_sentences = split_into_sentences(example_ocr_text)
    list_ocr_sentences = number_ocr_sentences(split_sentences)
    for sentence in list_ocr_sentences:
        print(f"listed sentences: {sentence}")
    
    for ocr_sentence, corrected_sentence in aligned_pairs:
        print(f"OCR Sentence: {ocr_sentence}")
        print(f"Corrected Sentence: {corrected_sentence}")
