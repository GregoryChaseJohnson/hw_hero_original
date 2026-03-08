import json
import os
import sys

# Helper function to escape HTML characters
def escape_html(text):
    """Escapes HTML special characters in the provided text."""
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#39;"))

# Generate HTML with corrections displayed for each sentence
def generate_html_with_corrections(data):
    html_output = ""

    # CSS styles for monospaced font and alignment
    styles = """
    <style>
        body {
            font-family: 'Courier New', Courier, monospace;
            white-space: pre-wrap;
            line-height: 1.2;
            padding: 20px;
        }
        .correction-line, .original-line {
            display: block;
            position: relative;
        }
        .correction-char, .original-char {
            display: inline-block;
            width: 0.6em;
            text-align: center;
        }
        .correction-char {
            color: green;
            font-weight: bold;
            position: relative;
            top: -0.6em;
        }
        .deletion {
            text-decoration: line-through;
            color: red;
        }
    </style>
    """

    # Iterate through each sentence in the JSON data
    for sentence_data in data["sentences"]:
        original_text = sentence_data["original_sentence"]
        corrections = sentence_data["corrections"]
        sentence_html = ""

        # Prepare a list to hold correction and original characters
        correction_line = []
        original_line = []

        # Create a mapping from position to correction
        correction_map = {}
        for correction in corrections:
            if correction["type"] == "insert" and "position" in correction:
                correction_map[correction["position"]] = correction
            elif "start" in correction:
                correction_map[correction["start"]] = correction

        idx = 0
        # Process each character in the original text
        while idx < len(original_text):
            char = original_text[idx]

            if idx in correction_map:
                correction = correction_map[idx]
                ctype = correction["type"]

                if ctype == "replace":
                    corrected_text = correction["corrected"]
                    length = correction["end"] - correction["start"]
                    for c in corrected_text:
                        correction_line.append(f"<span class='correction-char'>{escape_html(c)}</span>")
                    for _ in range(length):
                        original_line.append(f"<span class='original-char'>{escape_html(original_text[idx])}</span>")
                        idx += 1

                elif ctype == "delete":
                    length = correction["end"] - correction["start"]
                    for _ in range(length):
                        original_line.append(f"<span class='original-char deletion'>{escape_html(original_text[idx])}</span>")
                        idx += 1
                    correction_line.extend(["<span class='correction-char'> </span>"] * length)

                elif ctype == "insert":
                    corrected_text = correction["corrected"]
                    if corrected_text.strip() in {".", ",", "!", "?", ";", ":"}:
                        original_line.append(f"<span class='original-char'>{escape_html(corrected_text)}</span>")
                        correction_line.append("<span class='correction-char'> </span>")
                    else:
                        for c in corrected_text:
                            correction_line.append(f"<span class='correction-char'>{escape_html(c)}</span>")
                        original_line.extend(["<span class='original-char'> </span>"] * len(corrected_text))
                    idx += 1  # Ensure idx moves forward even with insertions

            else:
                correction_line.append("<span class='correction-char'> </span>")
                original_line.append(f"<span class='original-char'>{escape_html(char)}</span>")
                idx += 1

        # Combine correction line and original line
        sentence_html += "<div class='correction-line'>" + "".join(correction_line) + "</div>"
        sentence_html += "<div class='original-line'>" + "".join(original_line) + "</div>"

        # Add extra spacing between sentences
        html_output += f"{sentence_html}<br><br>"

    # Wrap the content with HTML and styles
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Correction Visualization</title>
        {styles}
    </head>
    <body>
        {html_output}
    </body>
    </html>
    """
    return html_content

# Determine paths for corrections.json and output HTML file based on script's directory
script_dir = os.path.dirname(os.path.abspath(__file__))
corrections_file_path = os.path.join(script_dir, "corrections.json")
output_html_path = os.path.join(script_dir, "test_output1.html")

# Load corrections data from corrections.json
if not os.path.exists(corrections_file_path):
    print("Error: corrections.json file not found. Please run parser.py first.")
    sys.exit(1)

try:
    with open(corrections_file_path, "r", encoding="utf-8") as file:
        corrections_data = json.load(file)
except json.JSONDecodeError as e:
    print(f"Error: Failed to parse 'corrections.json': {e}")
    sys.exit(1)

# Generate the corrected HTML content
full_html = generate_html_with_corrections(corrections_data)

# Write it to an output file
try:
    with open(output_html_path, "w", encoding="utf-8") as file:
        file.write(full_html)
    print(f"Generated {output_html_path}. Open this file in a browser to view the results.")
except Exception as e:
    print(f"Error writing to '{output_html_path}': {e}")
    sys.exit(1)
