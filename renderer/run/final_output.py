import pickle
from utils import apply_colors

if __name__ == "__main__":
    with open("final_output.pkl", "rb") as f:
        data = pickle.load(f)
        annotated_lines = data["annotated_lines"]
        final_sentences = data["final_sentences"]

    # Just display the final sentences with colors applied
    for i, (annotated_line, final_sentence) in enumerate(zip(annotated_lines, final_sentences), start=1):
        # Print the final annotated line
        annotated_line_str = apply_colors(annotated_line)
        final_sentence_str = apply_colors(final_sentence)

        print(annotated_line_str)
       
        print(final_sentence_str)

        print()
