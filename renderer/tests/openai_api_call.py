import base64
import json
from openai import OpenAI

client = OpenAI()

# Function to encode the image
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# Function to save data to a JSON file (overwrites existing file)
def save_to_json(file_path, data):
    with open(file_path, "w") as json_file:  # 'w' ensures the file is overwritten
        json.dump(data, json_file, indent=4)

# Path to your image
image_path = "/home/keithuncouth/Downloads/hwt_9.jpg"

# Getting the base64 string
base64_image = encode_image(image_path)

# OCR API call
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Extract the handwritten text from the image below. Do not include any additional information, labels, or formatting. Provide only the plain text content.",
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    },
                },
            ],
        }
    ],
    temperature=0,
    top_p=1
)

# Save OCR output to JSON (overwriting the file)
ocr_output = response.choices[0].message.content
save_to_json("ocr_output.json", {"ocr_text": ocr_output})

# Function to correct text
def correct_text(ocr_text):
    prompt = (
        "Correct the grammar sentence by sentence correcting unnatural sentences. "
        "Keep the corrections simple, use casual English, and retain the original sentences' overall structure. "
        "Avoid using semi-colons unless absolutely necessary. Leave end-of-text partial or incomplete sentences as they are; do not make assumptions.\n\n"
        f"Text to correct:\n{ocr_text}"
    )
    correction_response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0,
        top_p=1
    )
    return correction_response.choices[0].message.content

# Correct the OCR output
corrected_text = correct_text(ocr_output)

# Save corrected text to JSON (overwriting the file)
save_to_json("corrected_text.json", {"corrected_text": corrected_text})

print("OCR output and corrected text have been saved to JSON files (overwritten).")

print("\nOCR Output:")
print(ocr_output)

print("\nCorrected Text:")
print(corrected_text)
