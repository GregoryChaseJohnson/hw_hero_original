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

OCR_EMPTY_SENTINELS = {
    "",
    "Please provide the text of the student essay that you would like corrected.",
}

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
    extracted_text = (data.get("student_essay") or "").strip()
    if extracted_text in OCR_EMPTY_SENTINELS:
        return ""
    return extracted_text


# Correct Text
def correct_text(source_text):
    """
    Correct the grammar and structure of OCR-generated text.
    """
    normalized_source = (source_text or "").strip()
    if not normalized_source or normalized_source in OCR_EMPTY_SENTINELS:
        raise ValueError("No OCR text was extracted from the image.")

    system_prompt = """You are an English essay correction assistant for student writing.

Correct only clear errors in grammar, spelling, verb tense, subject-verb agreement, articles, prepositions, punctuation, capitalization, and word form.

Preserve the student's original wording whenever it is understandable and acceptable.

Do not rewrite for style, tone, fluency, vocabulary level, or preference.

Do not replace acceptable words or phrases with synonyms.

Do not change contractions to full forms or full forms to contractions.

Do not change intensifiers or quantity phrases such as very, really, a lot of, many, much, unless the original phrase is clearly incorrect in context.

When the original wording and a possible alternative are both acceptable, keep the original wording.

Output only the corrected essay text with no extra words, labels, or formatting.

Do not include headings, labels, numbering, bullet points, explanations, or a change list."""

    user_prompt = f"Correct this student essay.\n\n{normalized_source}"

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            }
        ],
        temperature=0,
        max_completion_tokens=1200
    )
    return response.choices[0].message.content
