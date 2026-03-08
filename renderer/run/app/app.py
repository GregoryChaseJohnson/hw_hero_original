import os
import sys
from flask import Flask, render_template, jsonify, request
import json
import importlib

# Make sure Python can find your modules (assuming they're in the same directory or a subfolder)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

APP_DIR = os.path.dirname(__file__)
RUN_DIR = os.path.abspath(os.path.join(APP_DIR, ".."))
OUTPUT_JSON_PATH = os.path.join(APP_DIR, "output.json")
SENTENCE_MAPPING_PATH = os.path.join(RUN_DIR, "sentence_mapping.json")

from correction_service import get_correction_explanation
from generate_explanation import generate_correction_explanation_single  # <--- Use correct file name

app = Flask(__name__)

@app.route("/")
def index():
    """
    Serves the main frontend page.
    """
    return render_template("index.html")

@app.route("/data.json")
def get_data():
    """
    Fetches and serves sentence/correction data from 'output.json' (adjust path as needed).
    """
    try:
        with open(OUTPUT_JSON_PATH, "r") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": "Failed to load output.json", "details": str(e)}), 500

@app.route("/sentence_mapping.json")
def get_sentence_mapping():
    """
    Fetches and serves OCR/corrected sentence mapping from '../sentence_mapping.json'.
    """
    try:
        with open(SENTENCE_MAPPING_PATH, "r") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": "Failed to load sentence_mapping.json", "details": str(e)}), 500

@app.route("/highlight_click", methods=["POST"])
def highlight_click():
    """
    Handles highlight-box clicks from the frontend. 
    Calls `get_correction_explanation` to retrieve the relevant sentence/block data,
    then runs a multi-step LLM explanation via `generate_correction_explanation_single`.
    """
    try:
        # 1) Parse the incoming JSON payload (blockType, blockIndex, sentenceIndex)
        data = request.get_json()
        print("[DEBUG] Received highlight click:", data)

        # 2) Retrieve correction details (sentence/block) from JSON metadata
        correction_info = get_correction_explanation(data)
        print("[DEBUG] Correction result:", correction_info)

        # 3) If there's an error (e.g. block not found), send it back
        if "error" in correction_info:
            return jsonify(correction_info), 400

        # 4) Extract fields for the explanation function
        # 4) Extract fields for the explanation function
        block_type = data.get("blockType")
        ocr_sentence = correction_info.get("ocr_sentence")
        corrected_sentence = correction_info.get("corrected_sentence")
        correction_block = correction_info.get("correction_block")
        correction_entry = correction_info.get("correction_entry")  # THIS IS MISSING!

        # 5) Generate explanation using the multi-step approach
        explanation = generate_correction_explanation_single(
            block_type, ocr_sentence, corrected_sentence, correction_block, correction_entry
        )

        before_text = ""
        after_text = ""
        if block_type == "replacement":
            before_text = correction_block.get("replaced_text", "")
            after_text = correction_block.get("corrected_text", "")
        elif block_type == "insert":
            before_text = ""
            after_text = correction_block.get("insert_text", "")
        elif block_type == "delete":
            before_text = correction_block.get("delete_text", "")
            after_text = ""

        result = {
            "explanation": explanation,
            "before_text": before_text,
            "after_text": after_text,
        }

        # 6) Return the explanation as JSON
        return jsonify(result)
    except Exception as e:
        print("[ERROR] Failed to process highlight click:", str(e))
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

@app.route("/analyze_text", methods=["POST"])
def analyze_text():
    """
    Runs the existing main.py pipeline using user-submitted text as OCR input.
    This preserves local default behavior of main.py when run directly.
    """
    payload = request.get_json(silent=True) or {}
    submitted_text = (payload.get("submitted_text") or "").strip()
    if not submitted_text:
        return jsonify({"error": "submitted_text is required"}), 400

    try:
        # Import from renderer/run/main.py (RUN_DIR is already on sys.path).
        import main as pipeline_main  # type: ignore
        pipeline_main = importlib.reload(pipeline_main)

        original_perform_ocr = pipeline_main.perform_ocr
        original_use_test_data = pipeline_main.use_test_data
        original_cwd = os.getcwd()

        try:
            # Ensure sentence_mapping.json is written into renderer/run/.
            os.chdir(RUN_DIR)
            pipeline_main.use_test_data = False
            pipeline_main.perform_ocr = lambda _image_path: submitted_text
            pipeline_main.main()
        finally:
            pipeline_main.perform_ocr = original_perform_ocr
            pipeline_main.use_test_data = original_use_test_data
            os.chdir(original_cwd)

        return jsonify({"ok": True})
    except Exception as e:
        print("[ERROR] Failed to run analyze_text pipeline:", str(e))
        return jsonify({"error": "Failed to run pipeline", "details": str(e)}), 500

if __name__ == "__main__":
    """
    Runs the Flask app (development mode).
    In production, use a WSGI server (e.g. Gunicorn) instead:
      gunicorn -b 0.0.0.0:5000 app:app
    """
    app.run(debug=True, host="0.0.0.0", port=5000)
