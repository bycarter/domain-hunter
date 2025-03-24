import nltk
import pandas as pd

nltk.download('words')

from nltk.corpus import words

word_list = set(words.words())
vowels = 'aeiou'

four_letter_words = [w.lower() for w in word_list if len(w) == 4 and w.isalpha()]
one_vowel_words = [w for w in four_letter_words if sum(c in vowels for c in w) == 1]
three_char_words = [w.translate({ord(v): None for v in vowels}) for w in one_vowel_words]

df = pd.DataFrame({
    'original_word': one_vowel_words,
    'three_char_word': three_char_words
})

df.to_csv('../data/three_char_words.csv', index=False)
