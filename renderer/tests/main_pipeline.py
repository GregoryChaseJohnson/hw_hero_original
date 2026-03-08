import subprocess
import os

def run_script(script, args=None):
    """
    Runs a Python script with optional arguments and captures its output.
    """
    command = ["python3", script]
    if args:
        command.extend(args)

    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error running {script}:")
        print(result.stderr)
        exit(1)
    print(f"Output of {script}:\n{result.stdout}\n")
    return result.stdout

def main_pipeline(image_path, processed_data_file):
    """
    Orchestrate the pipeline from OCR to rendering.
    """
    print("Starting the pipeline...\n")

    # Step 1: OCR Extraction and Text Correction
    print("Step 1: Extracting OCR and correcting text...")
    run_script("openai_api_call.py")

    # Ensure OCR and corrected text files exist
    if not os.path.exists("ocr_output.json") or not os.path.exists("corrected_text.json"):
        print("Error: OCR output or corrected text files missing.")
        exit(1)

    # Step 2: Sentence Alignment
    print("Step 2: Aligning sentences...")
    run_script("seq_alignment.py")

    # Ensure sentence pairs file exists
    if not os.path.exists("sentence_pairs.json"):
        print("Error: Sentence pairs file missing.")
        exit(1)

    # Step 3: Difference Highlighting
    print("Step 3: Highlighting differences...")
    run_script("sentence_parse2.py")

    # Ensure fused differences file exists
    if not os.path.exists("fused_differences.json"):
        print("Error: Fused differences file missing.")
        exit(1)

    # Step 4: Tokenized Sentence Processing
    print("Step 4: Processing tokenized sentences...")
    run_script("test_blocks_json.py")

    # Ensure processed data file exists
    if not os.path.exists(processed_data_file):
        print(f"Error: Processed data file '{processed_data_file}' missing.")
        exit(1)

    # Step 5: Rendering Corrections
    print("Step 5: Rendering corrections...")
    run_script("render_json.py", args=[processed_data_file])

    print("\nPipeline completed successfully.")

if __name__ == "__main__":
    # Path to the image file for OCR and the processed JSON output
    image_path = "/home/keithuncouth/Downloads/IMG_1258.jpg"
    processed_data_file = "processed_data.json"

    # Run the pipeline
    main_pipeline(image_path, processed_data_file)
