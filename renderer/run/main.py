import pickle
import json
from openai_api_call import perform_ocr, correct_text
from seq_alignment_reverse import align_sentences, clean_aligned_pairs, create_sentence_mapping
from diff_lib_refactor import generate_report # type: ignore
from block_creation import create_blocks
from data_loader import DataLoader
from renderer import process_sentences, save_renderer_output
from annotated_line_space_cleanup import post_process
from align_overhang import finalize_transformation
from prepare_tokenized_output import (
    assign_block_indices,
    detect_blocks_by_type,
    detect_replacement_blocks,
    detect_insert_blocks,
    detect_delete_blocks,
    split_for_display,
    #print_sentence_debug,
    prepare_json_output
)

use_test_data = False

test_ocr_text = """Recently, there are many music and K-pop singer coming out. Also, many people including youth are enjoying and affected by it. As the world keeps affected by K-pop, some people are concerned about K-pop music's bad influence because it can have the bad effect. But, for my opinion, I strongly believe that K-pop has more positive effect than harm on the youth.

Firstly, it can inspire confidence and hope. In my life, I'm having hard time due to the homework and school test. But, I sometimes get rested by hearing K-pop music and getting hope by it. Also, during COVID-19 pandemic, I was having hard time by its regulation. But when BTS's song named 'Permission to Dance', I can feel the hope to end the pandemic.

Secondly, it can make the whole culture more interest to youths. In my school, how many girl classmates gather and hang out to talk about their favorite K-pop singer or songs. Also, they collect their money or go to other place merchandise product of singer. This can trigger youths to make more friends and making them to be more socialized, which is important to later on the work.

Third and lastly, it can make Korean youth to think again about their traditional culture and proud of. Like recent I heard many about the Pusion.
"""
test_corrected_text = """Recently, there have been many new music and K-pop singers coming out. Also, a lot of people, including young people, are enjoying it and being influenced by it. As the world continues to be affected by K-pop, some people are concerned about its negative influence because it can have bad effects. But in my opinion, I strongly believe that K-pop has a more positive impact than harm on youth.

Firstly, it can inspire confidence and hope. In my life, I'm having a hard time with homework and school tests. But I sometimes find comfort in listening to K-pop music and feeling hopeful because of it. Also, during the COVID-19 pandemic, I struggled with the restrictions. But when I heard BTS's song "Permission to Dance," I felt hopeful about the end of the pandemic.

Secondly, it can make the whole culture more interesting to young people. In my school, many of my female classmates gather and hang out to talk about their favorite K-pop singers or songs. They also save up their money to buy merchandise from their favorite artists. This can encourage young people to make more friends and become more social, which is important for their future careers.

Lastly, it can make Korean youth rethink their traditional culture and feel proud of it. Recently, I've heard a lot about Pusion.
"""
image_path = "/home/keithuncouth/hw_hero_original/renderer/run/image0.jpeg"

def main():
    # Steps 1 & 2: OCR and correct
    if use_test_data:
        ocr_output = test_ocr_text
        corrected_text = test_corrected_text
    else:
        ocr_output = perform_ocr(image_path)
        print("OCR Output:")
        print(ocr_output)
        corrected_text = correct_text(ocr_output)
        print("\nCorrected Text:")
        print(corrected_text)

    # Step 3: Align sentences
    matches = align_sentences(ocr_output, corrected_text)
    print("\nAligned Sentences:")
    for ocr_sentence, corrected_sentence in matches:
        print(f"OCR Sentence: {ocr_sentence}")
        print(f"Corrected Sentence: {corrected_sentence}")
    
    cleaned_pairs = clean_aligned_pairs(matches)
    sentence_mapping = create_sentence_mapping(cleaned_pairs)

    # Step 4: Generate a report
    report, tokenized_output = generate_report(matches)
    print("\nGenerated Report:")
    print(report)

    # Step 5: Create blocks
    final_tokens_by_sentence = []
    blocks_by_sentence = []
    for sentence_tokens in tokenized_output:
        blocks = create_blocks(sentence_tokens)
        final_tokens_by_sentence.append(sentence_tokens)
        blocks_by_sentence.append(blocks)

    # Step 6: Render and capture the returned lines
    all_annotated_lines, all_final_sentences = process_sentences(
        final_tokens_by_sentence, blocks_by_sentence
    )
    annotated_lines = all_annotated_lines
    final_sentences = all_final_sentences

    # Step 7: Post-process
    annotated_lines, final_sentences, blocks_by_sentence = post_process(
        annotated_lines, final_sentences, blocks_by_sentence
    )
    save_renderer_output(annotated_lines, final_sentences, blocks_by_sentence)

    # Step 8: Final transformation
    print("\nRunning Final Transformation Stage...")
    annotated_lines, final_sentences = finalize_transformation(annotated_lines, final_sentences)

    # Step 9: Split merged alignment units into single-sentence display containers.
    annotated_lines, final_sentences, sentence_mapping = split_for_display(
        annotated_lines, final_sentences, sentence_mapping
    )
    sentence_mapping_path = "sentence_mapping.json"
    with open(sentence_mapping_path, "w", encoding="utf-8") as f:
        json.dump(sentence_mapping, f, indent=4, ensure_ascii=False)
    print(f"Sentence mapping saved to {sentence_mapping_path}")

    annotated_blocks_all = []
    for ann_line in annotated_lines:
        ann_blocks = detect_blocks_by_type(ann_line, valid_types={"corrected"})
        annotated_blocks_all.append(ann_blocks)

    final_blocks_all = []
    for fin_line in final_sentences:
        fin_blocks = detect_blocks_by_type(fin_line, valid_types={"replace"})
        final_blocks_all.append(fin_blocks)

    # Step 10: Assign block indices
    for ann_blocks, fin_blocks in zip(annotated_blocks_all, final_blocks_all):
        assign_block_indices(ann_blocks, fin_blocks)

    for ann_line in annotated_lines:
        for i, token in enumerate(ann_line):
            token["index"] = i

    for fin_line in final_sentences:
        for i, token in enumerate(fin_line):
            token["index"] = i

    # 2) Detect replacement blocks
    replacement_ann_blocks_all = []
    replacement_fin_blocks_all = []
    for ann_line, fin_line in zip(annotated_lines, final_sentences):
        ann_blocks, fin_blocks = detect_replacement_blocks(ann_line, fin_line)
        replacement_ann_blocks_all.append(ann_blocks)
        replacement_fin_blocks_all.append(fin_blocks)

    # 3) Detect insert + delete blocks
    insert_blocks_all = []
    delete_blocks_all = []
    for fin_line in final_sentences:
        ins_blks = detect_insert_blocks(fin_line)
        del_blks = detect_delete_blocks(fin_line)
        insert_blocks_all.append(ins_blks)
        delete_blocks_all.append(del_blks)

    # 4) Optional debug of replacement blocks
    #for idx, (ann_blocks, fin_blocks, final_line, annotated_line) in enumerate(
        #zip(
            #replacement_ann_blocks_all,
            #replacement_fin_blocks_all,
            #final_sentences,
            #annotated_lines
        #)
    #):
        #print_sentence_debug(idx, final_line, ann_blocks, fin_blocks, annotated_line)

    # 5) Prepare final JSON
    output_data = prepare_json_output(
        replacement_ann_blocks_all,
        replacement_fin_blocks_all,
        insert_blocks_all,
        delete_blocks_all,
        final_sentences,
        annotated_lines
    )

    # 6) Write output.json
    json_path = "/home/keithuncouth/hw_hero_original/renderer/run/app/output.json"
    with open(json_path, "w") as f:
        json.dump(output_data, f, indent=4)

    print(f"\n[INFO] Wrote {json_path} successfully.")

if __name__ == "__main__":
    main()
