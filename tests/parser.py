import os
import json
import spacy
from Levenshtein import distance as levenshtein_distance

# Load SpaCy's English model
nlp = spacy.load('en_core_web_sm')

def tokenize_text(text):
    """Tokenizes text into sentences and tokens using SpaCy."""
    doc = nlp(text)
    sentences = []
    for sent in doc.sents:
        tokens = [token.text for token in sent]
        sentences.append(tokens)
    return sentences

def classify_token(token_text):
    """Classifies the token as 'punctuation' or 'word'."""
    doc = nlp(token_text)
    token = doc[0]
    return 'punctuation' if token.is_punct else 'word'

def get_token_cost(token1, token2):
    """Assigns a substitution cost based on token similarity."""
    if token1 == token2:
        return 0
    subtype1 = classify_token(token1)
    subtype2 = classify_token(token2)
    if subtype1 == subtype2:
        if subtype1 == 'punctuation':
            return 1  # Lower cost for punctuation substitution
        else:
            # Use Levenshtein distance for minor word misspellings
            distance = levenshtein_distance(token1.lower(), token2.lower())
            max_len = max(len(token1), len(token2))
            normalized_distance = distance / max_len
            return 1 if normalized_distance < 0.4 else 2
    return 2  # Higher cost for different token types

def align_tokens(seq1, seq2):
    """Aligns two token sequences and identifies corrections."""
    n, m = len(seq1), len(seq2)
    score = [[0] * (m + 1) for _ in range(n + 1)]
    
    # Initialization for insertion and deletion costs
    for i in range(1, n + 1):
        token_type = classify_token(seq1[i - 1])
        score[i][0] = score[i - 1][0] + (2 if token_type == 'word' else 1)
    for j in range(1, m + 1):
        token_type = classify_token(seq2[j - 1])
        score[0][j] = score[0][j - 1] + (2 if token_type == 'word' else 1)

    # Filling the score matrix with substitution costs
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            sub_cost = get_token_cost(seq1[i - 1], seq2[j - 1])
            score[i][j] = min(
                score[i - 1][j] + (2 if classify_token(seq1[i - 1]) == 'word' else 1),  # Deletion
                score[i][j - 1] + (2 if classify_token(seq2[j - 1]) == 'word' else 1),  # Insertion
                score[i - 1][j - 1] + sub_cost  # Substitution
            )

    # Traceback to get alignment
    alignment = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            sub_cost = get_token_cost(seq1[i - 1], seq2[j - 1])
            if score[i][j] == score[i - 1][j - 1] + sub_cost:
                if sub_cost == 0:
                    alignment.append(('equal', seq1[i - 1], seq2[j - 1], i - 1, j - 1))
                else:
                    alignment.append(('replace', seq1[i - 1], seq2[j - 1], i - 1, j - 1))
                i -= 1
                j -= 1
                continue
        if i > 0 and score[i][j] == score[i - 1][j] + (2 if classify_token(seq1[i - 1]) == 'word' else 1):
            alignment.append(('delete', seq1[i - 1], None, i - 1, None))
            i -= 1
        elif j > 0 and score[i][j] == score[i][j - 1] + (2 if classify_token(seq2[j - 1]) == 'word' else 1):
            alignment.append(('insert', None, seq2[j - 1], None, j - 1))
            j -= 1
    alignment.reverse()
    return alignment

def classify_corrections(corrections):
    """Adds subtype information to corrections."""
    for correction in corrections:
        if correction['type'] == 'insert':
            correction['subtype'] = classify_token(correction.get('corrected', ''))
        elif correction['type'] == 'replace':
            correction['subtype'] = classify_token(correction.get('corrected', ''))
    return corrections

def generate_corrections_json(original_text, corrected_text):
    orig_sentences = tokenize_text(original_text)
    corr_sentences = tokenize_text(corrected_text)
    corrections_data = {'sentences': []}

    max_len = max(len(orig_sentences), len(corr_sentences))
    for idx in range(max_len):
        orig_tokens = orig_sentences[idx] if idx < len(orig_sentences) else []
        corr_tokens = corr_sentences[idx] if idx < len(corr_sentences) else []

        corrections = align_tokens(orig_tokens, corr_tokens)
        classified_corrections = []
        for op, orig, corr, oi, ci in corrections:
            if op == 'equal':
                continue  # Skip equal entries for correction data
            correction = {'type': op}
            if op == 'replace' or op == 'delete':
                correction['original'] = orig
                correction['start'] = oi
                if op == 'replace':
                    correction['corrected'] = corr
                    correction['end'] = ci
            elif op == 'insert':
                correction['corrected'] = corr
                correction['start'] = ci
            classified_corrections.append(correction)
        
        classified_corrections = classify_corrections(classified_corrections)
        sentence_data = {
            'sentence_number': idx + 1,
            'original_sentence': ' '.join(orig_tokens),
            'corrected_sentence': ' '.join(corr_tokens),
            'corrections': classified_corrections
        }
        corrections_data['sentences'].append(sentence_data)

    return corrections_data

def main():
    # Set paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_dir = os.path.join(script_dir, "input_data")
    output_file = os.path.join(script_dir, "corrections.json")
    original_path = os.path.join(input_dir, "original.txt")
    corrected_path = os.path.join(input_dir, "corrected.txt")

    # Check if input files exist
    if not os.path.isfile(original_path):
        print(f"Error: '{original_path}' does not exist.")
        return
    if not os.path.isfile(corrected_path):
        print(f"Error: '{corrected_path}' does not exist.")
        return

    # Load texts
    with open(original_path, "r", encoding="utf-8") as f:
        original_text = f.read()
    with open(corrected_path, "r", encoding="utf-8") as f:
        corrected_text = f.read()

    # Generate and save corrections data
    corrections_data = generate_corrections_json(original_text, corrected_text)
    try:
        with open(output_file, "w", encoding="utf-8") as file:
            json.dump(corrections_data, file, indent=2, ensure_ascii=False)
        print(f"Corrections data successfully written to {output_file}.")
    except Exception as e:
        print(f"Error writing to '{output_file}': {e}")

if __name__ == "__main__":
    main()
