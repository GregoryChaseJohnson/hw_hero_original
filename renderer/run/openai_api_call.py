import base64
import json
import mimetypes
import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

PROJECT_ENV = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=PROJECT_ENV)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

OCR_SYSTEM_PROMPT = """
You are a structured OCR extraction engine.
Extract text exactly as written. Preserve line breaks and spelling.
Do NOT correct, normalize, summarize, or rewrite.
Return JSON only.
"""


def _encode_image(image_path: str) -> tuple[str, str]:
    mime, _ = mimetypes.guess_type(image_path)
    if mime is None:
        mime = "image/jpeg"
    with open(image_path, "rb") as image_file:
        b64 = base64.b64encode(image_file.read()).decode("utf-8")
    return mime, b64


# Perform OCR using OpenAI API
def perform_ocr(image_path):
    """
    Extract handwritten text from an image via vision OCR and return plain essay text.
    """
    mime, base64_image = _encode_image(image_path)

    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": OCR_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Extract only the handwritten student essay. "
                            "Return JSON with schema: {\"student_essay\": \"...\"}."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{base64_image}"},
                    },
                ],
            },
        ],
        max_tokens=1500,
    )

    raw = response.choices[0].message.content
    data = json.loads(raw)
    return (data.get("student_essay") or "").strip()


# Correct Text
def correct_text(ocr_text):
    """
    Correct the grammar and structure of OCR-generated text.
    """
    prompt = (
        "Correct the text below for grammar and clearly unnatural ESL usage using minimal edits.\n"
        "Do not paraphrase or rewrite sentences.\n"
        "Keep paragraph breaks unchanged.\n"
        "Return only the corrected text.\n\n"
        f"{ocr_text}"
    )

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an ESL grammar correction engine.\n\n"
                    "Correct grammatical errors and clearly unnatural ESL constructions\n"
                    "while preserving the author's wording, sentence structure, and meaning.\n\n"
                    "Allowed corrections:\n"
                    "- grammar errors\n"
                    "- verb tense or agreement errors\n"
                    "- article usage (a/an/the)\n"
                    "- prepositions\n"
                    "- pluralization\n"
                    "- word form errors\n"
                    "- clearly unnatural phrasing typical of ESL writing\n\n"
                    "Rules:\n"
                    "- Prefer minimal edits, but adjust nearby words when needed for\ncorrect agreement, countability, or natural ESL usage.\n"
                    "- Do not rewrite sentences unless necessary to correct an error.\n"
                    "- Do not change the author's meaning or style.\n"
                    "- Do not simplify or paraphrase sentences.\n"
                    "- Preserve the original sentence structure whenever possible.\n"
                    "- Keep paragraph breaks exactly the same.\n\n"
                    "If a phrase is grammatically possible but clearly unnatural for standard written English, adjust it with minimal edits.\n\n"
                    "Output only the corrected text."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0,
        max_completion_tokens=1200
    )
    return response.choices[0].message.content
