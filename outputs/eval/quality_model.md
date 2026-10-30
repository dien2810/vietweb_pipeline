# Model-based quality signals on the hand-labelled pages

Training: 15000 Wikipedia articles of 20231101.vi (2 file(s); at least 1000 characters after the stage-3b line rules) and 15000 stage-7 documents not in the labelled set. Held-out accuracy of the classifier: 0.986 on 2000 Wikipedia articles, 0.952 on 2000 web documents. Trigram model: 255147 sentences, vocabulary 89457 syllables.

Labelled pages found in outputs/runs/wet_200_final/processed: 409 (285 poor).

| Signal | AUC, all | AUC, pages the rules keep (pass) | AUC, pages the rules remove (fail) |
|---|---:|---:|---:|
| fastText P(web) | 0.640 | 0.676 | 0.616 |
| Trigram perplexity | 0.583 | 0.541 | 0.628 |

Removing the same number of labelled pages as the rules (181 of 409):

| Method | Poor among removed | Poor among kept |
|---|---:|---:|
| Rules (stage 7) | 0.829 | 0.592 |
| fastText P(web) | 0.762 | 0.645 |
| Trigram perplexity | 0.762 | 0.645 |

On 3000 random kept documents: P(web) >= 0.9 for 92.5%; median perplexity 236 (Wikipedia held-out 124).
