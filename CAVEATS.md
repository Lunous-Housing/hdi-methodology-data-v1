# Caveats and Limitations -- HDI v1 Data Deposit

Condensed from the paper's limitations record. The paper is authoritative; section
pointers are to `docs/papers/hdi-methodology-v1/`.

1. **Structural, not individual.** The HDI measures how hard housing conditions push a
   community toward homelessness. Who falls into homelessness under that pressure is
   a separate question shaped by individual vulnerability (paper SS1).
2. **Cross-sectional, not causal.** The within-county temporal null is a detection
   limit. The data show which places have harder housing conditions; whether changing
   a place's conditions would change its homelessness rate is a different question
   that cross-sectional data cannot answer (paper SS6.4, SS8.3).
3. **Small-county noise (SS7.6).** ACS 5-year estimates carry large relative error in
   small counties. Quartile and threshold statements are robust patterns, but
   individual county scores should be read as approximate.
4. **Completeness classes matter.** SS7 analyses use only `complete` rows (2024: 2,967
   of 3,144). `partial` and `insufficient` rows are present but are below
   analysis-grade.
5. **Composite under missingness.** The composite averages available dimensions
   (renormalized) and never zero-fills. Under-instrumented places trend more
   distressed, so zero-fill would bias the places of most interest (paper SS3.5).
6. **Equal weights.** The three dimensions are weighted equally. Regression-informed
   weights were tested and suspended because the evidence for each dimension comes
   from different kinds of analysis; equal thirds is the principled default when the
   evidence is imprecise (paper SS5.3, SS9.5).
7. **Dropped dimensions.** Displacement Pressure (D3, no adequate eviction source) and
   Economic Vitality were dropped. EV raw inputs remain as lineage columns only.
8. **Within-state validation ceiling.** Signal selection, normalization, and weighting
   all use the national county panel. A supplementary within-state test (Washington
   only) explains very little variation in PIT rates (R-squared about 0.07-0.08) --
   as expected, because within one state rents vary too little county-to-county to
   reveal the link. The validated signal lives in the cross-state contrast (paper
   SS9.5).
9. **ACS measurement structure.** Occupied-unit counts and household counts are the
   same number in the ACS. Demand-side bias understates demand while excluded
   vacancies overstate shortage; net direction is unknown (paper SS5.5, SS9.2).
10. **PIT limitations (bright-spot panel).** Point-in-Time homelessness counts are
    single-night snapshots that are broadly understood to undercount the population
    experiencing homelessness. 2021 unsheltered coverage is inconsistent per geography
    (COVID waiver) -- a trend caveat handled per geography-year.
11. **Paper-vs-live divergence.** The live Hub keeps evolving with canonical
    corrections (already 2,962 vs 2,967 complete counties two weeks post-build). The
    severe+MAX confirmation bounds the variant gap at Spearman rho = 0.99. Cite the
    frozen file when referencing the paper.
12. **Reproducibility posture.** These files are preserved as primary artifacts.
    Re-derivation from the documented public sources and operations is possible but
    will produce different bytes as upstream data and scope evolve (e.g., future
    admission of CT planning regions). The deposit exists so the cited result is
    always retrievable.
