# HDI Methodology Paper v1 — Data Deposit

Frozen data artifacts for the Lunous Housing Distress Index (HDI) methodology paper
(`docs/papers/hdi-methodology-v1/`). These are the **exact bytes the paper's analysis
read** — primary artifacts, never regenerated. The platform's live data continues to
evolve; these files do not. Byte-exactness here is a *citation* property: a reader of the
paper must be able to retrieve precisely what was analyzed.

**DOI:** _to be minted by the Zenodo deposit (see DEPOSIT-STEPS.md; fill in here after)_
**License (recommended):** CC BY 4.0 — standard for citable research data; Peter confirms
at deposit time.

## Files

| file | bytes | sha256 (git-LF content at freeze commit) |
|---|---|---|
| `2026-06-11-hdi-vnext-scores-county-v2-severe-equal.parquet` | 6,336,020 | `f3b7525f7e7c44e50bcaf0fe552bdfba1b2c1ed35670ce36305694e3eb71bf7e` |
| `2026-05-25-hdi-vnext-scores-national-v2-full.parquet` | 9,391,809 | `ad25b89feedba90ec5655d48c1dbd6fce2f0c017376ea1b9493810d33b5e02d3` |
| `2026-06-07-hdi-coc-pit-panel.parquet` | 55,296 | `faff053322dbf52460cb3075ca19c1161f30bf652326dd5a733342ce7cc84385` |

All three verified 2026-07-17 via `git show HEAD:<path> | sha256` against the repo at the
freeze commit; the first two also match the hashes recorded in the paper's manifest
(`docs/papers/hdi-methodology-v1/manifest/manifest.json`) and tracker respectively. The
paper's manifest is **verified, not regenerated**, per the freeze rule.

### Roles

1. **`…county-v2-severe-equal.parquet` — the primary artifact.** The sole cited §7 scores
   file: county HDI v2 scores (severe + MAX cost burden variant, equal weights),
   2010–2024, all 3,144 counties per year with completeness classes. Every §7.1 statistic
   reproduces from this file to printed precision (2024: 2,967 `complete` / 157 `partial`
   / 20 `insufficient`; mean 59.3, median 60.2, sd 12.2, skew −0.57, min 8.0, max 97.4 —
   re-verified 2026-07-17). Column documentation: `CODEBOOK.md`.
2. **`…national-v2-full.parquet` — supporting artifact.** The fuller scores run the cited
   county-baselines document derives from, and input to the 2026-06-10 study-repair
   scripts. De-cited from §7 directly but load-bearing for lineage; included so the
   deposit's derivation chain has no dangling reference.
3. **`…coc-pit-panel.parquet` — supporting artifact.** Input to the §7.5 "bright spot"
   analysis run `d554c37d4c0b`, whose three output JSONs are manifest-cited. Included for
   the same lineage-completeness reason.

## Citation

> Lunous. *Housing Distress Index methodology paper v1 — data deposit.* Zenodo, 2026.
> DOI: _(fill after mint)_. Primary artifact sha256 `f3b7525f…71bf7e`.

## Known divergence from the live platform

The Hub's live API serves scores that continue to evolve with canonical-data corrections.
Two weeks after the paper build, the live 2024 universe already differed by five counties
(2,962 vs 2,967 complete). This is expected platform behavior, not an erratum: the paper
cites this frozen file, and the severe+MAX confirmation run bounds the paper-vs-live gap
(Spearman ρ = 0.99). See `CAVEATS.md`.
