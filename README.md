# HDI Methodology Paper v1 — Data Deposit

Frozen data artifacts for the Lunous Housing Distress Index (HDI) methodology paper
(`docs/papers/hdi-methodology-v1/`). The three parquet files under "Files" are the **exact
bytes the paper's analysis read** — primary artifacts, never regenerated. The platform's
live data continues to evolve; these files do not. Byte-exactness here is a *citation*
property: a reader of the paper must be able to retrieve precisely what was analyzed. From
version 1.2 the deposit also carries the files behind the paper's version 1.1 erratum; see
"Files added in version 1.2" below.

**DOI (all versions, resolves to the latest):** [10.5281/zenodo.21461377](https://doi.org/10.5281/zenodo.21461377).
The paper's version 1.0 cites the first version's DOI,
[10.5281/zenodo.21461378](https://doi.org/10.5281/zenodo.21461378); the three parquet files
are the same bytes in every version.
**License:** CC BY 4.0, as set on the Zenodo record in every version. (The paper's version
1.0, Appendix A, lists the scores file as CC0; its erratum, item E-13, corrects that.) The
Redfin-derived values carry Redfin's non-commercial terms (see "Redfin terms" below).

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

## Files added in version 1.2: the erratum's county tables

Zenodo version 1.2 adds the files behind the paper's version 1.1 erratum: its Tables E.1
and E.3 and the county figures in its items. With them, those numbers can be recomputed
from this deposit alone. The three parquet files above are unchanged. The erratum's metro
models (its Table E.2) read the CBSA panel the paper's metro evidence used, which is not
published; the erratum identifies it by its SHA-256, and the deposit carries the models'
outputs only.

| file | bytes | sha256 | role |
|---|---|---|---|
| `export-2.0-extract.parquet` | 4,033,649 | `8299e91c45c247cc0e2a1784ef26f22a8325feb7c86edeeac06d4dcc7b345d22` | County-years 2010–2024 from the Hub's public export 2.0 (run `20260924T182315Z-302195`), on the Hub's current definitions. Columns: `CODEBOOK.md`. |
| `export-2.0-extract.sha256` | 93 | `bdfb5dc988916eeecd288ea470b20998089e5450fc9e608428d1c2fb5b1c4274` | The extract's SHA-256. The script also pins it and refuses any other extract. |
| `export-2.0-manifest.json` | 26,466 | `fdab9f22e775d041d01a3370dfd33fae1cc1e000cbd780590d04c048eee7e076` | The export's manifest, verbatim: run ID, the SHA-256 of each export file, sources and source terms. For provenance; the script does not read it. |
| `hdi-county-baselines-v1.json` | 1,413 | `9d989bcc4d6c381b7f25d9d7af75bf8ae9861b0ec34f2ae2e864f04056cc0edd` | The Hub's version 1 clip points, which the script reads (hash-checked) and compares with the primary file's own. |
| `hdi_erratum_county_table.py` | 43,716 | `9277a1e6ce2395c418ad83c3b2b8ba323abdda40f8fdad1203bfde41a6fab692` | The script that computes the four outputs below. |
| `deposit-clips.json` | 2,882 | `7ecf1b3722f13bb48d2a4493418a14df29acf9f9aeead3b9f365de753fa7d7ce` | Table E.1 and its reproduction checks. |
| `county-table.json` | 3,900 | `c9f4d4568134bcb3dd99e2085f9d91c771525a704706432affa5a89c292e4139` | Table E.3. |
| `county-table.txt` | 1,906 | `55bd56bdb7e67daa6180598d96548e8613f919bbbc24c6c2c9118ead0b184d47` | Table E.3, as text. |
| `facts.json` | 2,555 | `d9de78a4014a6e4ca270231a2dff9efe0b624f34b0ce5088a8325d01a387d0f4` | The county figures the erratum's items cite. |
| `cbsa-models.json` | 6,396 | `ac3f1590fd7675ad7d74bd47e37a89fbb101eab2f7649d448523ffd6280f0e34` | The metro models of Table E.2 (outputs only). |
| `cbsa-models.txt` | 2,828 | `4e804db109f592f374541d995d393c016b2b45c99fa1ed946a54183f4ef0892d` | The same, as text. |

Sizes and hashes are of the files as published (LF line endings for the text files).

**To recompute.** Put these files in one folder with the primary scores file and the
national supporting file above, and run:

    python hdi_erratum_county_table.py compute --data-dir .

It verifies the SHA-256 of each input and rewrites `deposit-clips.json`,
`county-table.json`, `county-table.txt` and `facts.json` byte for byte. This was tested
on Windows with Python 3.12.10 and pandas 3.0.5 and 3.0.6, numpy 2.5.3, scipy 1.18.1,
pyarrow 25.0.1 and requests 2.34.2, and with an older set (pandas 2.2.3, numpy 2.1.3,
scipy 1.14.1, pyarrow 18.1.0); all gave identical outputs. With other versions, if a
file differs, compare its numbers at the precision the erratum prints them. The script's `fetch` command rebuilt the extract from the export files; it works
only while the Hub's public export still serves run `20260924T182315Z-302195`, and it
refuses to overwrite an existing extract, so run it only in an empty folder. The extract
here is the lasting copy.

**Redfin terms.** The extract's `median_sale_price` column and its `price_to_income`
values are derived in part from Redfin County Market Data, redistributed by Lunous subject
to Redfin's non-commercial data sharing license, as in the primary file (the paper's
Appendix A, footnote 4) and the Hub's public export (the manifest's `sourceRestrictions`).
Users must comply with that restriction when using or distributing those values. The
dimension and composite scores are Lunous-derived composites and are not subject to it.

## Citation

> Lunous. *Housing Distress Index methodology paper v1 — data deposit.* Zenodo, 2026.
> DOI: [10.5281/zenodo.21461377](https://doi.org/10.5281/zenodo.21461377) (all versions;
> version 1.0, the one the paper's version 1.0 cites:
> [10.5281/zenodo.21461378](https://doi.org/10.5281/zenodo.21461378)). Primary artifact
> sha256 `f3b7525f…71bf7e`.

## Known divergence from the live platform

The Hub's live data continues to evolve with canonical-data corrections. Two weeks after
the paper build, the live 2024 universe already differed by five counties (2,962 vs 2,967
complete).

Since 2026-09-24 the live Hub also uses different definitions (AHIH-498):
- both Affordability ratios divide by ACS all-household median income;
- the rental vacancy rate follows the Census definition;
- scores are normalized against a new baseline.

The primary scores file (`…county-v2-severe-equal.parquet`) keeps the definitions the
paper analysed: renter median income for rent, HUD AMI for price, and scores scaled between
its own 2010–2019 clip points (the erratum's Table E.1). The erratum's extract, added in
version 1.2, is on the Hub's current definitions. The paper's version 1.1 erratum describes
both sets of definitions (see `CAVEATS.md` item 13). Cite the primary scores file when
referencing the paper's analysis.

## Versions

These are the values of Zenodo's own "Version" field for this record. They are distinct
from the paper's version numbers. The concept DOI
[10.5281/zenodo.21461377](https://doi.org/10.5281/zenodo.21461377) always resolves to the
latest version.

| Zenodo version | Change |
|---|---|
| 1.0 | Original deposit (2026-07). Version DOI [10.5281/zenodo.21461378](https://doi.org/10.5281/zenodo.21461378), the one the paper's version 1.0 cites. |
| 1.1 | Corrected `CAVEATS.md`. Version DOI [10.5281/zenodo.21461764](https://doi.org/10.5281/zenodo.21461764). |
| 1.2 | Accompanies the paper's version 1.1 erratum (2026-09). Documentation corrections: the `price_to_income`, `rent_to_income` and vacancy definitions in `CODEBOOK.md`, the price denominator of the supporting national file, `CAVEATS.md` items 11 and 13, and this README (including the DOIs above: earlier versions called 10.5281/zenodo.21461378 the concept DOI, but it is version 1.0's own). Adds the erratum's county-table files (see "Files added in version 1.2"). The three original parquet files are unchanged, and their SHA-256 values above were re-verified. Version DOI [10.5281/zenodo.22968265](https://doi.org/10.5281/zenodo.22968265). |
