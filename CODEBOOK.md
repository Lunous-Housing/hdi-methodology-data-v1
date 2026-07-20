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
| `sig_rent_to_income_acs_raw/_norm` | `rent_to_income` — median gross rent ÷ median renter household income (ACS) | Affordability |
| `sig_price_to_income_raw/_norm` | `price_to_income` — median home value ÷ median household income | Affordability |
| `sig_cost_burden_rate_raw/_norm` | `cost_burdened_share` — share of renter households paying ≥30% of income | Cost Burden |
| `sig_severe_cost_burden_rate_raw/_norm` | severe cost-burdened share (≥50%); this file is the **severe + MAX** variant: the Cost Burden dimension takes MAX(normalized ≥30% share, normalized severe share) | Cost Burden |
| `sig_rental_vacancy_rate_raw/_norm` | rental vacancy rate; **inverted** at normalization (low vacancy = high distress). The `.v1` normalization bypassed the A4/A5 holdout (accepted limitation, CONSTRAINTS.md) | Availability |

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
- `2026-06-07-hdi-coc-pit-panel.parquet` — CoC-level PIT panel (55 KB) feeding the §7.5
  bright-spot analysis; HUD CoC PIT counts by CoC-year with the paper's inclusion flags.
