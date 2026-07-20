# Caveats and Limitations — HDI v1 Data Deposit

Condensed from the paper's own limitations record. The paper is authoritative; section
pointers are to `docs/papers/hdi-methodology-v1/` (deposited alongside via the repo/PDF).

1. **The HDI measures structural housing distress, not individual outcomes.** Housing
   supply mismatch is treated as the population-level structural predictor; individual
   vulnerabilities determine *who* is affected. Do not use these scores to explain or
   predict individual homelessness (project core thesis; paper §1).
2. **Cross-sectional, not causal.** The within-county temporal null in the paper is a
   *detection limit*, not evidence that affordability doesn't matter — do not read these
   data as implying interventions are futile (paper framing rule).
3. **Small-county noise (§7.6).** ACS 5-year estimates carry large relative error in
   small counties; quartile and threshold statements are robust patterns, not precise
   per-county predictions.
4. **Completeness classes are load-bearing.** §7 analyses use only `complete` rows
   (2024: 2,967 of 3,144). `partial`/`insufficient` rows are present and inspectable —
   absence is visible, never silent — but not analysis-grade.
5. **Composite under non-random missingness.** The composite averages available
   dimensions (renormalized), never zero-fills: under-instrumented places trend more
   distressed, so all-or-nothing nulling or zero-fill would bias exactly the places of
   interest (paper §3.5).
6. **Equal weights.** The regression-informed weighting scheme is suspended; scores are
   equal-weight across dimensions (accepted limitation).
7. **Dropped dimensions.** Displacement Pressure (D3) — no adequate eviction source —
   and Economic Vitality were dropped; EV raw inputs remain as lineage columns only.
8. **Threshold calibrations are Washington-specific.** Validation ceilings (~7–8% R²
   within-state) and calibration choices derive from WA data; national application of
   thresholds is illustrative (guardrail matrix, appendix D).
9. **ACS measurement structure.** Occupied-unit counts and household counts are near-
   tautological in ACS; demand-side bias understates demand while excluded vacancies
   overstate shortage — net direction unknown, documented rather than "corrected"
   (DATA_INTEGRITY.md).
10. **PIT limitations (bright-spot panel).** Point-in-Time homelessness counts are
    single-night snapshots with known undercounts; 2021 unsheltered coverage is
    inconsistent per geography (COVID waiver) — a trend caveat handled per
    geography-year, not a blanket exclusion.
11. **Paper-vs-live divergence is expected.** The live Hub keeps evolving with canonical
    corrections (already 2,962 vs 2,967 complete counties two weeks post-build). The
    severe+MAX confirmation bounds the variant gap at Spearman ρ = 0.99. Cite the frozen
    file, not the live API, when referencing the paper.
12. **Reproducibility posture.** These files are preserved as primary artifacts.
    Re-derivation from surviving raw data is possible in principle but will not be
    byte-identical as upstream data and scope evolve (e.g., future admission of CT
    planning regions); that is precisely why the deposit exists.
