# Language identification at stage 4: heuristic vs GlotLID (CC-MAIN-2026-39)

37456 documents reach stage 4 (after stages 3 and 3b).

| Threshold | Kept by heuristic | Kept by GlotLID (P(vie_Latn)) |
|---:|---:|---:|
| 0.3 | 33938 | 33906 |
| 0.5 | 33609 | 33849 |
| 0.6 | 33396 | 33817 |
| 0.7 | 33029 | 33781 |
| 0.8 | 32425 | 33722 |
| 0.9 | 31387 | 33636 |

At threshold 0.6:

- Both keep: 33380; both remove: 3623
- Heuristic keeps, GlotLID removes: 16
- Heuristic removes, GlotLID keeps: 437
- Agreement 0.9879; Cohen's kappa 0.934

GlotLID top label of the documents the heuristic removes:

- eng_Latn: 2439
- vie_Latn: 489
- ind_Latn: 136
- deu_Latn: 117
- fra_Latn: 104
- spa_Latn: 86
- kor_Hang: 64
- rus_Cyrl: 58
- ita_Latn: 57
- lat_Latn: 47
- por_Latn: 45
- nld_Latn: 43

GlotLID top label of the documents the heuristic keeps but GlotLID removes:

- hun_Latn: 3
- cmn_Hani: 2
- vie_Latn: 2
- ces_Latn: 2
- frp_Latn: 1
- pol_Latn: 1
- cmo_Latn: 1
- bdq_Latn: 1
- rus_Cyrl: 1
- yor_Latn: 1
- tur_Latn: 1
