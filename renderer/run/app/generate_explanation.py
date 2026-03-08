import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from correction_service import (
    get_correction_explanation,
    build_before_after_for_clicked_block
)

PROJECT_ENV = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=PROJECT_ENV)

def _build_openai_client():
    """
    Build an OpenAI client from the project .env file.
    Re-loading dotenv keeps behavior consistent across block types.
    """
    load_dotenv(dotenv_path=PROJECT_ENV, override=False)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(f"OPENAI_API_KEY is missing (expected in {PROJECT_ENV})")
    return OpenAI(api_key=api_key)


def _chat_completion(model, messages, temperature, max_completion_tokens):
    """Single completion helper so all paths use the same key-loading protocol."""
    client = _build_openai_client()
    return client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_completion_tokens=max_completion_tokens,
    )

def build_replacement_prompt(before_text, after_text, custom_sentence, corrected_sentence):
    """
    Single-stage replacement explanation:
    1) Single-sentence explanation from direct context
    """
    compact_context = (
        f"ORIGINAL SENTENCE: \"{custom_sentence}\"\n"
        f"CORRECTED SENTENCE: \"{corrected_sentence}\"\n"
        f"BEFORE phrase: \"{before_text}\"\n"
        f"AFTER phrase: \"{after_text}\"\n"
    )

    # STEP 1: one-sentence explanation from direct context.
    explanation_prompt = (
        compact_context +
        "Write one sentence (max 24 words) explaining the correction.\n"
        "Requirements:\n"
        f"- Include \"{before_text}\" and \"{after_text}\" in double quotes\n"
        "- No pedagogical filler\n"
        "- No extra sentences"
    )
    print("\n--- EXPLANATION PROMPT ---")
    print(explanation_prompt.upper())
    
    explanation_response = _chat_completion(
        model="gpt-5.2",
        messages=[{"role": "user", "content": explanation_prompt}],
        temperature=0.2,
        max_completion_tokens=90,
    )
    one_sentence_explanation = explanation_response.choices[0].message.content.strip()
    print("\n--- EXPLANATION RESPONSE ---")
    print(one_sentence_explanation)
    
    return one_sentence_explanation

def build_deletion_prompt(original_snippet, custom_sentence, corrected_sentence):
    """
    Build a deletion prompt.
    """
    base_prompt = (
        f"Sentence: \"{custom_sentence}\"\n\n"
        f"Corrected sentence: \"{corrected_sentence}\"\n\n"
        f"Removed: \"{original_snippet}\"\n\n"
    )
    instructions = (
        "Identify the direct cause of the change and state it as a single concise diagnosis. "
        "Do not justify, elaborate, generalize, or add benefits. "
        "Do not mention clarity, naturalness, correctness, or standard usage. "
        "Output one short, plain statement describing only what was fixed and why, "
        "at the most concrete level necessary, and stop."
    )
    return base_prompt + instructions

def build_insertion_prompt(inserted_text, custom_sentence, corrected_sentence):
    """
    Build an insertion prompt.
    """
    base_prompt = (
        f"Incorrect sentence: \"{custom_sentence}\"\n\n"
        f"Correct sentence: \"{corrected_sentence}\"\n\n"
        f"Inserted text: \"{inserted_text}\"\n\n"
    )
    instructions = (
        "Explain in one or two short, plain English sentences why the inserted text is needed to correct the sentence based on usage patterns. Avoid broader commentary."
    )
    return base_prompt + instructions

def generate_correction_explanation_single(block_type, ocr_sentence, corrected_sentence, correction_block, correction_entry=None):
    """
    Generate the final correction explanation.
    For 'replacement' blocks, uses the output from build_replacement_prompt directly.
    For 'delete' and 'insert', builds the appropriate prompt and shows its output.
    """
    if correction_entry is not None:
        before_sentence, after_sentence = build_before_after_for_clicked_block(
            correction_entry, correction_block, block_type
        )
    else:
        # Conservative fallback if correction_entry is unavailable.
        if block_type == "replacement":
            before_sentence = ocr_sentence
            after_sentence = corrected_sentence
        elif block_type == "insert":
            before_sentence = ocr_sentence
            after_sentence = corrected_sentence
        elif block_type == "delete":
            start = correction_block.get("final_start")
            deleted_text = correction_block.get("delete_text", "")
            before_sentence = corrected_sentence[:start] + deleted_text + corrected_sentence[start:]
            after_sentence = corrected_sentence
        else:
            raise ValueError(f"UNSUPPORTED BLOCK TYPE: {block_type}")

    print("DEBUG: BEFORE SENTENCE (clicked block inverted):")
    print(before_sentence)
    print("DEBUG: AFTER SENTENCE (fully corrected):")
    print(after_sentence)

    if block_type == "replacement":
        before_text = correction_block.get("replaced_text", "")
        after_text = correction_block.get("corrected_text", "")
        # For replacement blocks, directly use build_replacement_prompt's output.
        explanation = build_replacement_prompt(before_text, after_text, before_sentence, after_sentence)
    elif block_type == "delete":
        original_snippet = correction_block.get("delete_text", "")
        final_prompt = build_deletion_prompt(original_snippet, before_sentence, after_sentence)
        print("\n--- FINAL DELETION PROMPT ---")
        print(final_prompt.upper())
        response = _chat_completion(
            model="gpt-5.2",
            messages=[{"role": "user", "content": final_prompt}],
            temperature=0,
            max_completion_tokens=100
        )
        explanation = response.choices[0].message.content.strip()
        print("\n--- FINAL DELETION RESPONSE ---")
        print(explanation)
    elif block_type == "insert":
        inserted_text = correction_block.get("insert_text", "")
        final_prompt = build_insertion_prompt(inserted_text, before_sentence, after_sentence)
        print("\n--- FINAL INSERTION PROMPT ---")
        print(final_prompt.upper())
        response = _chat_completion(
            model="gpt-5.2",
            messages=[{"role": "user", "content": final_prompt}],
            temperature=0,
            max_completion_tokens=100
        )
        explanation = response.choices[0].message.content.strip()
        print("\n--- FINAL INSERTION RESPONSE ---")
        print(explanation)
    else:
        raise ValueError(f"UNSUPPORTED BLOCK TYPE: {block_type}")

    return explanation

# --- Example Test Harness (Adjust for your own usage) ---
if __name__ == "__main__":
    test_data = {"blockType": "replacement", "blockIndex": 0, "sentenceIndex": 0}
    
    correction_info = get_correction_explanation(test_data)
    if "error" in correction_info:
        print("ERROR FROM CORRECTIONS_SERVICE:", correction_info)
    else:
        block_type = test_data["blockType"]
        ocr_sentence = correction_info["ocr_sentence"]
        corrected_sentence = correction_info["corrected_sentence"]
        correction_block = correction_info["correction_block"]
        correction_entry = correction_info.get("correction_entry")  # Needed for delete blocks.

        explanation = generate_correction_explanation_single(
            block_type,
            ocr_sentence,
            corrected_sentence,
            correction_block,
            correction_entry
        )

        print("\nEXPLANATION FOR SINGLE BLOCK:")
        print(explanation)
