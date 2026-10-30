# Counting unit in stage 7: syllables vs words (28948 stage-7 documents of outputs/runs/wet_200_final/processed)

## Cost and tokens

- Syllables: 0.25 ms per document (one process)
- Words (underthesea): 15.80 ms per document with 2 process(es), about 32 ms of CPU; 98.2 M characters in all
- Median tokens per document: 464 syllables, 335 words; syllables per word 1.38

## Documents each token-based rule would remove (current thresholds)

| Rule | Syllables | Words |
|---|---:|---:|
| gopher_word_count | 5.6% | 11.2% |
| gopher_mean_word_length | 1.2% | 0.1% |
| gopher_symbol_ratio | 0.0% | 0.1% |
| gopher_stopwords | 3.9% | 4.6% |
| gopher_top_2gram | 0.9% | 0.9% |
| gopher_top_3gram | 1.5% | 2.3% |
| gopher_top_4gram | 3.4% | 4.4% |

Kept by stage 7: 25246 with syllables, 24058 with words; kept only with syllables 1357, kept only with words 169. With syllables and the word-count minimum scaled to 73: 24113 kept, 563 decisions differ from words.

## Hand-labelled pages (409; label 1 = poor, sampled near the syllable thresholds)

| Unit | Poor pages removed | Acceptable pages removed | Decision matches label |
|---|---:|---:|---:|
| syllables | 150/285 | 31/124 | 0.594 |
| words | 193/285 | 28/124 | 0.707 |
| syllables, word count >= 73 | 209/285 | 39/124 | 0.719 |
