# data_loader.py

class DataLoader:
    def __init__(self, final_sentences, blocks_by_sentence):
        """
        Initializes the DataLoader with preprocessed data.

        Args:
            final_sentences (List[str]): List of sentences with ANSI color codes.
            blocks_by_sentence (List[List[Block]]): List of blocks corresponding to each sentence.
        """
        self.final_sentences = final_sentences
        self.blocks_by_sentence = blocks_by_sentence
        self.current = 0
        self.total = len(final_sentences)

    def __iter__(self):
        return self

    def __next__(self):
        if self.current < self.total:
            sentence = self.final_sentences[self.current]
            blocks = self.blocks_by_sentence[self.current]
            self.current += 1
            return sentence, blocks
        else:
            raise StopIteration
