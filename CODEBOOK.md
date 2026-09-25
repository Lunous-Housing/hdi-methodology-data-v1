# Codebook — `2026-06-11-hdi-vnext-scores-county-v2-severe-equal.parquet`

47,160 rows = 3,144 U.S. counties × 15 years (2010–2024), one row per county-year.
35 columns. Authored 2026-07-17 from the frozen file's schema + the v2 vocabulary
(`docs/methodology/hdi-dimensions.md`); no file was regenerated.

**Naming note (important):** column names predate the HDI v2 vocabulary correction — the
renames were deliberately deferred to a later refactor, so the columns carry *old* IDs.
The crosswalk below is normative. In particular `dim_financial_strain_score` is the
paper's **Cost Burden** dimension, and `dim_affordability_score` is the paper's
**Affordability** dimension (the ratio dimension). All scores are 0–100 with **higher =
more distress**.

## Identity

| column | meaning |
|---|---|
| `geo_id` | 5-digit county FIPS (string) |
| `geo_level` | always `"county"` in this file |
| `geo_name` | county display name |
| `year` | ACS 5-year vintage year, 2010–2024 |

## Signals (paper §4) — `_raw` = source-unit value, `_norm` = normalized 0–100 distress score

| column | paper signal (v2 vocabulary) | dimension |
|---|---|---|
| `sig_rent_to_income_acs_raw/_norm` | `rent_to_income` — 12 × median gross rent ÷ median renter household income (ACS B25064; B25119 renter-occupied) | Affordability |
| `sig_price_to_income_raw/_norm` | `price_to_income` — Redfin median sale price ÷ HUD AMI (the fiscal-year HUD median family income for the county's FMR area or HMFA). *Corrected in deposit version 1.2; earlier versions said "median home value ÷ median household income", which is wrong on both terms. See the paper's erratum, item E-2.* | Affordability |
| `sig_cost_burden_rate_raw/_norm` | `cost_burdened_share` — share of renter households paying ≥30% of income | Cost Burden |
| `sig_severe_cost_burden_rate_raw/_norm` | severe cost-burdened share (≥50%); this file is the **severe + MAX** variant: the Cost Burden dimension takes MAX(normalized ≥30% share, normalized severe share) | Cost Burden |
| `sig_rental_vacancy_rate_raw/_norm` | rental vacancy rate: vacant for rent ÷ (vacant for rent + renter-occupied), ACS B25004_002 ÷ (B25004_002 + B25003_003). This omits the "rented, not occupied" units (B25004_003) that the Census definition includes, so it runs slightly above the Census rate (erratum item E-8). **Inverted** at normalization (low vacancy = high distress). The `.v1` normalization bypassed the A4/A5 holdout (accepted limitation, CONSTRAINTS.md) | Availability |

## Dimension scores (paper §5)

| column | paper dimension | composition |
|---|---|---|
| `dim_affordability_score` (+`_completeness_class`) | **Affordability** | rent_to_income + price_to_income |
| `dim_financial_strain_score` (+`_completeness_class`) | **Cost Burden** | cost-burdened share, severe+MAX variant |
| `dim_availability_score` (+`_completeness_class`, `dim_availability_status`) | **Availability** | rental vacancy (inverted) |

Per-dimension `*_completeness_class` records whether that dimension could be scored for
the county-year; `dim_availability_status` carries the availability-specific status
detail.

## Composite

| column | meaning |
|---|---|
| `composite_equal` | **the HDI**: equal-weight mean of available dimension scores, renormalized (paper §5; regression-informed weights suspended — CONSTRAINTS.md). Null when `completeness_class = "insufficient"` |
| `completeness_class` | `complete` (all three dimensions scored — the paper's §7 analysis universe) \| `partial` \| `insufficient` |
| `peer_comparison_suppressed` | boolean; peer-comparison display suppression flag |
| `notes` | free-text row notes |

Missingness design (paper §3.5 / design-principles): the composite is the mean of
*available* dimensions — never zero-filled, never nulled by a single missing dimension —
because composite missingness is non-random (under-instrumented places trend more
distressed). Below the completeness minimum it publishes as `insufficient` with a null
score.

## Economic Vitality lineage columns (NOT scored — dropped dimension)

`sig_employment_growth_raw`, `sig_population_growth_raw`, `sig_lfpr_raw`,
`sig_net_agi_migration_raw`, `sig_wolfson_polarization_raw`, each with a paired
`*_data_available` boolean. These carry the raw inputs of the **dropped Economic
Vitality dimension** (paper history: EV → dropped; D3 Displacement Pressure also dropped
— no WA eviction source). They contribute **nothing** to any dimension or composite score
in this file; they are retained under the project's store-data-without-a-use-case
principle and for lineage transparency. `sig_wolfson_polarization_raw` is computed on
native cost brackets (never AMI-band aggregates — DATA_INTEGRITY.md rule).

## Supporting files

- `2026-05-25-hdi-vnext-scores-national-v2-full.parquet` — superset scores run (fuller
  signal/variant set, same identity model); source of the county-baselines derivation.
  Its `price_to_income` divides the Redfin median sale price by ACS all-household median
  income (B25119_001E), unlike the primary file, which divides by HUD AMI. Four of the five
  rows of the clip table printed in the paper's §4.5 (all but severe cost burden, which this
  file does not carry) come from this file, so they do not reproduce the primary file's
  scores. The clips that do are in the paper's erratum, Table E.1.
- `2026-06-07-hdi-coc-pit-panel.parquet` — CoC-level PIT panel (55 KB) feeding the §7.5
  bright-spot analysis; HUD CoC PIT counts by CoC-year with the paper's inclusion flags.

## Erratum extract (`export-2.0-extract.parquet`, added in deposit version 1.2)

One row per county-year, 2010–2024, taken from three tables of the Hub's public export 2.0
(run `20260924T182315Z-302195`) on the Hub's **current** definitions (AHIH-498), not the
paper's. The paper's erratum uses it for Table E.3 and the county figures in its items. The
export's own data dictionaries, listed in `export-2.0-manifest.json`, are the full
definitions; in brief:

| column(s) | meaning |
|---|---|
| `county_fips`, `year` | 5-digit county FIPS; ACS 5-year vintage year. |
| `rent_to_income_score`, `rent_to_income_raw_value` | `12 × median_gross_rent_monthly ÷ median_household_income`, and its 0–100 score. |
| `price_to_income_score`, `price_to_income_raw_value` | `median_sale_price ÷ median_household_income`, and its 0–100 score. Redfin terms apply (README). |
| `cost_burdened_share_*`, `severe_cost_burdened_share_*` | Renter households paying 30%+ and 50%+ of income on gross rent (B25070), and their scores. |
| `rental_vacancy_rate_*` | The Census rental vacancy rate, and its score (negated before scaling). |
| `d1_score`…`d3_score`, `d1_name`…`d3_name`, `composite_score` | The three dimension scores with their names, and the composite. |
| `median_gross_rent_monthly` | ACS median gross rent, B25064_001E, dollars per month. |
| `median_household_income` | ACS median household income, all households, B25119_001E; the denominator of both market ratios. |
| `median_sale_price` | Redfin median sale price, dollars. Redfin terms apply (README). |
| `pit_rate` | The county's PIT homelessness rate: `rate_value` from the export's `homelessness-landscape` table. |
| `acs_median_household_income`, `hud_area_median_income`, `hud_to_acs_ratio` | From the export's `geography-profile-series` table: ACS all-household median income, HUD's area median family income, and their ratio. |

Scores are scaled against the Hub's v2 baseline, so they are not comparable value for value
with the primary file's `_norm` columns.
