import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
try:
    from .correction_service import (
        get_correction_explanation,
        build_before_after_for_clicked_block
    )
except ImportError:
    from correction_service import (
        get_correction_explanation,
        build_before_after_for_clicked_block
    )

PROJECT_ENV = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=PROJECT_ENV)

DISPLAY_EXPLANATION_SYSTEM_PROMPT = (
    "Explain the correction for a student in a short, natural  way. "
    "Do not add praise, encouragement, filler introductions, or conversational openings like ‘Great job,’ ‘Nice catch,’ or ‘You’re close.’ "
    "Start immediately with the explanation. "
    "Avoid heavy grammar terminology unless absolutely necessary. "
    "If the correction is simple, give one easy rule to remember. "
    "If it’s more nuanced, give 2–3 short examples of natural usage."
)

KOREAN_EXPLANATION_SYSTEM_PROMPT = (
    "You transform English correction notes into short Korean explanations for Korean English learners.\n\n"

    "Write mostly in Korean.\n"
    "Keep all quoted English words, phrases, and corrected expressions exactly as provided.\n"
    "Do not translate full English example sentences into Korean unless necessary.\n"
    "Do not change or paraphrase quoted English expressions.\n\n"

    "Goal:\n"
    "Explain only what changed and why the corrected expression sounds more natural.\n\n"

    "Style:\n"
    "- 실제 한국인 영어 선생님처럼 짧고 바로 설명하세요.\n"
    "- 설명은 바로 시작하세요.\n"
    "- 최대 4문장까지만 쓰세요.\n"
    "- 불필요한 칭찬, 공감, 추임새는 쓰지 마세요.\n"
    "- 딱딱한 문어체나 교재 말투는 피하세요.\n"
    "- 문법 용어는 꼭 필요할 때만 쓰세요.\n"
    "- 설명이 너무 길어지지 않게 하세요.\n"
    "- '느낌', '뉘앙스', '자주 쓰는 말' 같은 모호한 표현은 꼭 필요할 때만 쓰세요.\n\n"

    "Structure:\n"
    "- 먼저 어떤 표현이 더 자연스러운지 설명하세요.\n"
    "- 그다음 왜 자연스러운지 짧게 설명하세요.\n"
    "- 필요하면 마지막에 아주 짧은 기억 팁 하나만 추가하세요.\n"
    "- 예시는 정말 필요할 때만 아주 짧게 추가하세요.\n\n"

    "Avoid:\n"
    "- 과한 친절함\n"
    "- AI 같은 설명 말투\n"
    "- 반복 설명\n"
    "- 의미 없는 완곡 표현\n"
)

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

def build_display_explanation(explanation_prompt_text, explanation_response_text):
    """
    Run a second-pass explanation rewrite for the UI display text using the
    original explanation prompt body plus the first-pass explanation output.
    """
    display_user_prompt = (
        f"{explanation_prompt_text} "
        f"{explanation_response_text}"
    )
    print("\n--- DISPLAY EXPLANATION PROMPT ---")
    print(display_user_prompt)

    response = _chat_completion(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": DISPLAY_EXPLANATION_SYSTEM_PROMPT},
            {"role": "user", "content": display_user_prompt},
        ],
        temperature=0,
        max_completion_tokens=140,
    )
    display_explanation = response.choices[0].message.content.strip()
    print("\n--- DISPLAY EXPLANATION RESPONSE ---")
    print(display_explanation)
    return display_explanation

def build_korean_explanation(display_prompt_text, display_response_text):
    """
    Run a third-pass Korean explanation using the display prompt and display response.
    """
    korean_user_prompt = (
        f"{display_prompt_text} "
        f"{display_response_text}"
    )
    print("\n--- KOREAN EXPLANATION PROMPT ---")
    print(korean_user_prompt)

    response = _chat_completion(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": KOREAN_EXPLANATION_SYSTEM_PROMPT},
            {"role": "user", "content": korean_user_prompt},
        ],
        temperature=0,
        max_completion_tokens=180,
    )
    korean_explanation = response.choices[0].message.content.strip()
    print("\n--- KOREAN EXPLANATION RESPONSE ---")
    print(korean_explanation)
    return korean_explanation

def build_replacement_prompt(before_text, after_text, custom_sentence, corrected_sentence):
    """
    Build the replacement explanation context block.
    """
    return (
        f"ORIGINAL SENTENCE: \"{custom_sentence}\"\n"
        f"CORRECTED SENTENCE: \"{corrected_sentence}\"\n"
        f"BEFORE phrase: \"{before_text}\"\n"
        f"AFTER phrase: \"{after_text}\"\n"
    )

def run_replacement_explanation(before_text, after_text, custom_sentence, corrected_sentence):
    explanation_prompt = build_replacement_prompt(
        before_text, after_text, custom_sentence, corrected_sentence
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
    
    return build_display_explanation(explanation_prompt, one_sentence_explanation)

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

def build_insertion_context(inserted_text, custom_sentence, corrected_sentence):
    """Build the context block for insertion explanations."""
    return (
        f"ORIGINAL SENTENCE: \"{custom_sentence}\"\n"
        f"CORRECTED SENTENCE: \"{corrected_sentence}\"\n"
        "BEFORE PHRASE: \"\"\n"
        f"AFTER PHRASE: \"{inserted_text}\"\n"
    )

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
        explanation = run_replacement_explanation(
            before_text, after_text, before_sentence, after_sentence
        )
        explanation_prompt_for_display = build_replacement_prompt(
            before_text, after_text, before_sentence, after_sentence
        )
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
        explanation = build_display_explanation(final_prompt, explanation)
        explanation_prompt_for_display = final_prompt
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
        explanation = build_display_explanation(final_prompt, explanation)
        explanation_prompt_for_display = final_prompt
    else:
        raise ValueError(f"UNSUPPORTED BLOCK TYPE: {block_type}")

    korean_explanation = build_korean_explanation(
        explanation_prompt_for_display,
        explanation,
    )
    return {
        "english_explanation": explanation,
        "korean_explanation": korean_explanation,
    }

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

        explanation_payload = generate_correction_explanation_single(
            block_type,
            ocr_sentence,
            corrected_sentence,
            correction_block,
            correction_entry
        )

        print("\nEXPLANATION FOR SINGLE BLOCK:")
        print(explanation_payload)
