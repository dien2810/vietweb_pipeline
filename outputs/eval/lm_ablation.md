# Small GPT trained on raw vs cleaned text (same pages, same tokenizer, same number of tokens)

Validation loss in nats per token (perplexity = e^loss); lower is better.

Wikipedia: held-out articles after the stage-3b line rules (sentence lines, as in the clean corpus); Wikipedia, full text: the same articles with headings, lists and short lines.

| Preset | Corpus | Seed | Tokens | Params (M) | Wikipedia | Wikipedia, full text | Clean web | Raw web | Seconds |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| cpu | clean | 0 | 3,000,000 | 7.29 | 5.965 (389) | 6.164 | 5.180 | 6.673 | 1218 |
| cpu | clean | 1 | 3,000,000 | 7.29 | 5.911 (369) | – | 5.127 | 6.560 | 1390 |
| cpu | raw | 0 | 3,000,000 | 7.29 | 6.597 (733) | 6.709 | 5.966 | 5.945 | 1263 |
| cpu | raw | 1 | 3,000,000 | 7.29 | 6.575 (717) | – | 5.948 | 5.925 | 1364 |

Mean over seeds, clean minus raw (negative = the cleaned corpus gives a lower loss):

- cpu, Wikipedia: -0.648 (clean 5.938, n = 2; raw 6.586, n = 2)
- cpu, Wikipedia, full text: -0.545 (clean 6.164, n = 1; raw 6.709, n = 1)
- cpu, clean web: -0.804 (clean 5.153, n = 2; raw 5.957, n = 2)
- cpu, raw web: +0.682 (clean 6.616, n = 2; raw 5.935, n = 2)
