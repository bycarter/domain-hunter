import nltk
import pandas as pd
import os
from utils import get_data_dir

def generate_three_char_words():
    try:
        nltk.download('words', quiet=True)
        
        from nltk.corpus import words
        
        word_list = set(words.words())
        vowels = 'aeiou'
        
        four_letter_words = [w.lower() for w in word_list if len(w) == 4 and w.isalpha()]
        one_vowel_words = [w for w in four_letter_words if sum(c in vowels for c in w.lower()) == 1]
        three_char_words = [w.lower().translate({ord(v): None for v in vowels}) for w in one_vowel_words]
        
        df = pd.DataFrame({
            'original_word': one_vowel_words,
            'three_char_word': three_char_words
        })
        
        output_path = os.path.join(get_data_dir(), 'three_char_words.csv')
        df.to_csv(output_path, index=False)
        print(f"Generated {len(three_char_words)} three-character words at {output_path}")
        return output_path
    except Exception as e:
        print(f"Error generating words: {e}")
        return None

if __name__ == "__main__":
    generate_three_char_words()