#!/usr/bin/env python3
"""AHIH-507 erratum: the county bivariate R^2 chain (paper Table 6.2) and the clip table
(paper section 4.5 / Table E.1), recomputed on the public export.

Plan: docs/superpowers/plans/2026-09-24-ahih-507-hdi-paper-erratum.md, Task 1.
Spec: docs/superpowers/specs/2026-09-24-ahih-507-hdi-paper-erratum-design.md, section 4
(and section 3 E-2, E-3, E-8, E-10).

Reimplements the bivariate R^2 chain of
docs/superpowers/evidence/2026-06-11-hdi-bivariate-aggregation-chain-severe-equal.py
(same `bivariate_r2` rule: Pearson r^2 over non-null rows, NaN below 10 rows) but reads
the county PIT rate from the public export instead of a live SQL connection, so the
result is reproducible from committed and downloadable files alone.

Two subcommands, run in order:

  fetch   -- downloads manifest.json and three export 2.0 parquet files from the public
             container, refuses on any hash mismatch against the pins below, and writes
             a small extract (docs/papers/hdi-methodology-v1/erratum/export-2.0-extract.parquet)
             plus the verbatim manifest and the extract's own SHA-256. Network required.

  compute -- reads only committed files (the extract, the deposit's primary parquet, the
             deposit's supporting national parquet, and the v1 baselines JSON), verifies
             their hashes, and writes deposit-clips.json, county-table.json,
             county-table.txt and facts.json. No network. A second run is byte-identical.

Usage (Git Bash, from the worktree root):
    PY=/h/ClaudeCode/AHI-Hub/.venv/Scripts/python.exe
    "$PY" scripts/analysis/hdi_erratum_county_table.py fetch
    "$PY" scripts/analysis/hdi_erratum_county_table.py compute

From the data deposit (Zenodo version 1.2), where this script ships in one folder with
its inputs and outputs, pass that folder: every input is read from it and every output
is written to it, and the outputs are byte-identical to the published ones:
    python hdi_erratum_county_table.py compute --data-dir .
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

import numpy as np
import pandas as pd
import requests
from scipy.stats import spearmanr

# ---------------------------------------------------------------------------
# Paths and pinned identities
# ---------------------------------------------------------------------------

_SCRIPT_PATH = Path(__file__).resolve()
# In the repository this file sits at scripts/analysis/; in the data deposit it sits in a
# flat folder, which can be too shallow for parents[2].
REPO_ROOT = _SCRIPT_PATH.parents[2] if len(_SCRIPT_PATH.parents) > 2 else _SCRIPT_PATH.parent

BASE_URL = "https://ahihubpublic.blob.core.windows.net/data"
RUN_ID = "20260924T182315Z-302195"

ERRATUM_DIR = REPO_ROOT / "docs" / "papers" / "hdi-methodology-v1" / "erratum"

DEPOSIT_PARQUET_PATH = (
    REPO_ROOT / "docs" / "superpowers" / "evidence"
    / "2026-06-11-hdi-vnext-scores-county-v2-severe-equal.parquet"
)
DEPOSIT_SHA256 = "f3b7525f7e7c44e50bcaf0fe552bdfba1b2c1ed35670ce36305694e3eb71bf7e"

# The deposit's *supporting* national file. Its own p1/p99 (county rows, 2010-2019) are
# what the paper's printed clip table (P04:293-297, PAPER_PRINTED_CLIPS below) actually
# came from for four of the five signals (E-3) -- it is on household income, not the
# primary file's HUD-AMI / renter-income constructions (E-1, E-2). Read-only, and
# already in git, so reading it in `compute` keeps `compute` on committed inputs.
NATIONAL_SUPPORTING_PARQUET_PATH = (
    REPO_ROOT / "docs" / "superpowers" / "evidence"
    / "2026-05-25-hdi-vnext-scores-national-v2-full.parquet"
)
NATIONAL_SUPPORTING_SHA256 = "ad25b89feedba90ec5655d48c1dbd6fce2f0c017376ea1b9493810d33b5e02d3"

V1_JSON_PATH = (
    REPO_ROOT / "src" / "functions" / "pipeline" / "baselines" / "hdi-county-baselines-v1.json"
)
# LF-normalized content (the file is `eol=lf` in the repository; the deposit copy is taken
# with `git show`), so a CRLF copy still verifies.
V1_JSON_SHA256_LF = "9d989bcc4d6c381b7f25d9d7af75bf8ae9861b0ec34f2ae2e864f04056cc0edd"

# facts.json records the supporting file by its repository path and hash, wherever it
# was read from, so a run from the deposit folder writes the same bytes.
NATIONAL_SUPPORTING_RECORD_PATH = (
    "docs/superpowers/evidence/2026-05-25-hdi-vnext-scores-national-v2-full.parquet"
)

# The manifest's runId and the three export files `fetch` downloads (plan Task 0).
EXPORT_FILE_HASHES: dict[str, str] = {
    "hdi-scores-county.parquet": "ea8881c1a1c427966dda0132b3c59037ec426c77b05be68b4bcf9f74090d84dd",
    "homelessness-landscape.parquet": "a30be1bf14b1bf119a69e6a550297a042f93fc649b78966af2fd671c904cefce",
    "geography-profile-series.parquet": "5ad2eeae14f50f651b11232d3b94be2713bb958e0e014601a87f4f932d7c60c4",
}

MANIFEST_FILENAME = "manifest.json"
MANIFEST_OUT_FILENAME = "export-2.0-manifest.json"
EXTRACT_FILENAME = "export-2.0-extract.parquet"
EXTRACT_SHA_FILENAME = "export-2.0-extract.sha256"
# The published extract (erratum reproducibility table; deposit v1.2). `compute` refuses
# any other extract, and a sidecar that records anything else, so replacing the extract
# and its .sha256 together cannot pass.
EXTRACT_SHA256 = "8299e91c45c247cc0e2a1784ef26f22a8325feb7c86edeeac06d4dcc7b345d22"


@dataclass(frozen=True)
class Layout:
    """Where `fetch` and `compute` read inputs and write outputs."""

    out_dir: Path
    deposit: Path
    national: Path
    v1_json: Path


# The repository layout (the default).
REPO_LAYOUT = Layout(
    out_dir=ERRATUM_DIR,
    deposit=DEPOSIT_PARQUET_PATH,
    national=NATIONAL_SUPPORTING_PARQUET_PATH,
    v1_json=V1_JSON_PATH,
)


def flat_layout(data_dir: Path) -> Layout:
    """One folder holding every input and output under its own file name: the layout
    of the data deposit's version 1.2."""
    return Layout(
        out_dir=data_dir,
        deposit=data_dir / DEPOSIT_PARQUET_PATH.name,
        national=data_dir / NATIONAL_SUPPORTING_PARQUET_PATH.name,
        v1_json=data_dir / V1_JSON_PATH.name,
    )

COUNTY_ID_LEN = 5
DISCOVERY_YEAR_MIN = 2010
DISCOVERY_YEAR_MAX = 2019
# Table E.1 prints the clip points at this many decimals. `compute` refuses unless the
# printed (rounded) values also reproduce the deposit's `_norm` columns (Codex P2, #568).
PRINTED_CLIP_DECIMALS = 8
HOLDOUT_YEARS: tuple[int, ...] = (2022, 2023, 2024)
HUD_RATIO_YEAR_MIN = 2010
HUD_RATIO_YEAR_MAX = 2024

MANIFEST_TIMEOUT_SECONDS = 120
FILE_TIMEOUT_SECONDS = 120

KING_COUNTY_FIPS = "53033"
KING_COUNTY_YEAR = 2024
# ACS 2020-2024 5-year B25119_003E (renter median household income), King County, WA: the
# public source value, as the Hub ingested it (tier1 raw/v1/53033/acs-b25119-2024.json,
# renterMedianIncome). `compute` refuses unless the deposit's implied rent denominator
# rounds to it -- the evidence that the deposit divides rent by renter income (E-1).
KING_COUNTY_ACS_RENTER_MEDIAN_2024 = 85547


# ---------------------------------------------------------------------------
# Signal / dimension constants
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SignalSpec:
    """One signal's deposit <-> export column pairing (plan Task 1, `SIGNALS`)."""

    id: str
    deposit_raw: str
    deposit_norm: str
    export_score: str
    export_raw: str
    negate: bool
    label: str
    v1_json_column: str


SIGNALS: tuple[SignalSpec, ...] = (
    SignalSpec(
        "price_to_income", "sig_price_to_income_raw", "sig_price_to_income_norm",
        "price_to_income_score", "price_to_income_raw_value", False,
        "price_to_income (Affordability)", "price_to_income",
    ),
    SignalSpec(
        "rent_to_income", "sig_rent_to_income_acs_raw", "sig_rent_to_income_acs_norm",
        "rent_to_income_score", "rent_to_income_raw_value", False,
        "rent_to_income (Affordability)", "rent_to_income_acs",
    ),
    SignalSpec(
        "cost_burdened_share", "sig_cost_burden_rate_raw", "sig_cost_burden_rate_norm",
        "cost_burdened_share_score", "cost_burdened_share_raw_value", False,
        "cost_burdened_share >=30% (Cost Burden)", "cost_burden_rate",
    ),
    SignalSpec(
        "severe_cost_burdened_share", "sig_severe_cost_burden_rate_raw",
        "sig_severe_cost_burden_rate_norm", "severe_cost_burdened_share_score",
        "severe_cost_burdened_share_raw_value", False,
        "severe_cost_burdened_share >=50% (Cost Burden, v2)", "severe_cost_burden_rate",
    ),
    SignalSpec(
        "rental_vacancy_rate", "sig_rental_vacancy_rate_raw", "sig_rental_vacancy_rate_norm",
        "rental_vacancy_rate_score", "rental_vacancy_rate_raw_value", True,
        "rental_vacancy_rate (Availability)", "rental_vacancy_rate",
    ),
)


@dataclass(frozen=True)
class DimensionSpec:
    """One dimension's deposit <-> export column pairing (plan Task 1, `DIMENSIONS`)."""

    id: str
    deposit_col: str
    export_col: str
    label: str


DIMENSIONS: tuple[DimensionSpec, ...] = (
    DimensionSpec("affordability", "dim_affordability_score", "d2_score",
                  "Affordability (equal avg of two signals)"),
    DimensionSpec("cost_burden", "dim_financial_strain_score", "d3_score",
                  "Cost Burden (severe+MAX)"),
    DimensionSpec("availability", "dim_availability_score", "d1_score",
                  "Availability (sole signal)"),
)

COMPOSITE_DEPOSIT_COL = "composite_equal"
COMPOSITE_EXPORT_COL = "composite_score"

# d1/d2/d3 = Availability/Affordability/Cost Burden is the export's own numbering
# (scripts/public_export/drift/mapping.py), not the frozen artifact's. `check_dimension_names`
# asserts it rather than trusting position.
EXPECTED_DIMENSION_NAMES: dict[str, str] = {
    "d1_name": "Availability",
    "d2_name": "Affordability",
    "d3_name": "Cost Burden",
}

# Column A of Table 6.2, exactly as v1.0 printed it (P06:224-234), plus the June 2026
# script's own unrounded output before the paper rounded it to 3dp
# (docs/superpowers/evidence/2026-06-11-hdi-bivariate-aggregation-chain-severe-equal.txt:9-17).
# n = 8,851 county-years (P06:219).
V1_PRINTED_TABLE_6_2: dict[str, Any] = {
    "n": 8851,
    "price_to_income": {"printed": "0.116", "txt": 0.1157},
    "rent_to_income": {"printed": "0.014", "txt": 0.0136},
    "cost_burdened_share": {"printed": "0.033", "txt": 0.0333},
    "severe_cost_burdened_share": {"printed": "0.030", "txt": 0.0295},
    "rental_vacancy_rate": {"printed": "0.001", "txt": 0.0008},
    "affordability_dim": {"printed": "0.090", "txt": 0.0901},
    "cost_burden_dim": {"printed": "0.032", "txt": 0.0317},
    "availability_dim": {"printed": "0.001", "txt": 0.0008},
    "composite": {"printed": "0.054", "txt": 0.0542},
}

# The paper's printed clip table, P04:293-297 (paper section 4.5). Four of the five rows
# match, to the printed six decimals, the deposit's supporting national file's own county
# 2010-2019 p1/p99 (`compute_national_supporting_clips`, which refuses otherwise); the
# severe row is not derivable from that
# file (it carries no severe columns) and the paper says it was independently verified
# instead (P04:299-302).
PAPER_PRINTED_CLIPS: dict[str, dict[str, Any]] = {
    "rent_to_income": {"clip_low": 0.148877, "clip_high": 0.470373, "n": 31254},
    "price_to_income": {"clip_low": 0.572437, "clip_high": 7.916303, "n": 22716},
    "cost_burdened_share": {"clip_low": 0.105263, "clip_high": 0.571174, "n": 31281},
    "severe_cost_burdened_share": {"clip_low": 0.026777, "clip_high": 0.337734, "n": 31287},
    "rental_vacancy_rate": {"clip_low": -0.249924, "clip_high": 0.0, "n": 31053},
}

# JSON keys carried at full float precision rather than rounded to 12 decimals -- these
# are the clip cut points themselves (the plan: "clip_low, clip_high (repr precision)"),
# not derived error/comparison numbers.
FULL_PRECISION_KEYS: frozenset[str] = frozenset({
    "clip_low", "clip_high",
    "v1_json_clip_low", "v1_json_clip_high",
    "paper_table_clip_low", "paper_table_clip_high",
})


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------


def derive_clips(values: pd.Series, negate: bool) -> tuple[float, float, int]:
    """p1/p99 via `numpy.percentile`'s default linear method, over non-null values
    (negated first when `negate`). Returns (clip_low, clip_high, n)."""
    x = pd.Series(values).dropna()
    if negate:
        x = -x
    n = int(len(x))
    if n == 0:
        return float("nan"), float("nan"), 0
    lo = float(np.percentile(x.to_numpy(dtype=float), 1))
    hi = float(np.percentile(x.to_numpy(dtype=float), 99))
    return lo, hi, n


def normalize(raw: pd.Series, lo: float, hi: float, negate: bool) -> pd.Series:
    """`clamp((x - lo) / (hi - lo) * 100, 0, 100)`, with `x = -raw` when negated."""
    x = -raw if negate else raw
    return ((x - lo) / (hi - lo) * 100.0).clip(lower=0.0, upper=100.0)


def max_abs_error(a: pd.Series, b: pd.Series) -> float:
    """Max absolute difference over rows where both are non-null. NaN if none."""
    a = pd.Series(a)
    b = pd.Series(b)
    mask = a.notna() & b.notna()
    if int(mask.sum()) == 0:
        return float("nan")
    return float((a[mask] - b[mask]).abs().max())


def bivariate_r2(x: pd.Series, y: pd.Series) -> tuple[float, int]:
    """Pearson r^2 over rows where both are non-null; NaN below 10 rows (the June
    script's rule, docs/superpowers/evidence/2026-06-11-...-severe-equal.py:55-60)."""
    x = pd.Series(x)
    y = pd.Series(y)
    mask = x.notna() & y.notna()
    n = int(mask.sum())
    if n < 10:
        return float("nan"), n
    r = np.corrcoef(x[mask].to_numpy(dtype=float), y[mask].to_numpy(dtype=float))[0, 1]
    return float(r ** 2), n


def check_dimension_names(export: pd.DataFrame) -> None:
    """Raise unless d1_name/d2_name/d3_name are uniformly Availability/Affordability/
    Cost Burden, so the B/C mapping never trusts column position alone."""
    for col, expected in EXPECTED_DIMENSION_NAMES.items():
        values = sorted(set(export[col].dropna().unique().tolist()))
        if values != [expected]:
            raise ValueError(
                f"{col} is not uniformly {expected!r}: found {values!r}. The county "
                "table's column mapping (d1=Availability, d2=Affordability, "
                "d3=Cost Burden) assumes this."
            )


def common_universe(
    deposit: pd.DataFrame, export: pd.DataFrame, outcome: str, years: Iterable[int],
) -> pd.DataFrame:
    """The county-years that are `complete` in the deposit, carry every export signal
    score, and have a non-null `outcome` in `export`, restricted to `years`. Inner join
    on (county, year): deposit's `geo_id` against export's `county_fips`."""
    years = list(years)
    score_cols = [s.export_score for s in SIGNALS]
    dep = deposit[
        (deposit["completeness_class"] == "complete") & deposit["year"].isin(years)
    ].copy()
    exp = export.dropna(subset=score_cols).copy()
    exp = exp[exp["year"].isin(years) & exp[outcome].notna()]
    return dep.merge(
        exp, left_on=["geo_id", "year"], right_on=["county_fips", "year"],
        how="inner", suffixes=("_dep", "_exp"),
    )


def export_own_universe(export: pd.DataFrame, outcome: str, years: Iterable[int]) -> pd.DataFrame:
    """The export's own analogue of `complete`: every signal score present and a
    non-null `outcome`, restricted to `years` (spec section 4.3's 'secondary line')."""
    years = list(years)
    score_cols = [s.export_score for s in SIGNALS]
    exp = export.dropna(subset=score_cols).copy()
    return exp[exp["year"].isin(years) & exp[outcome].notna()]


# ---------------------------------------------------------------------------
# JSON writing (determinism: sort_keys, indent=2, LF, trailing newline, floats
# rounded to 12 decimals except FULL_PRECISION_KEYS)
# ---------------------------------------------------------------------------


def _round_floats(obj: Any, decimals: int = 12,
                   full_precision_keys: frozenset[str] = frozenset()) -> Any:
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return round(obj, decimals)
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if k in full_precision_keys and isinstance(v, float):
                out[k] = None if (math.isnan(v) or math.isinf(v)) else v
            else:
                out[k] = _round_floats(v, decimals, full_precision_keys)
        return out
    if isinstance(obj, (list, tuple)):
        return [_round_floats(v, decimals, full_precision_keys) for v in obj]
    return obj


def write_json(path: Path, obj: Any, full_precision_keys: frozenset[str] = frozenset()) -> None:
    rounded = _round_floats(obj, full_precision_keys=full_precision_keys)
    text = json.dumps(rounded, sort_keys=True, indent=2) + "\n"
    with open(path, "w", newline="\n", encoding="utf-8") as f:
        f.write(text)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _verify_file_sha256(path: Path, expected: str, label: str) -> None:
    if not path.exists():
        raise SystemExit(f"REFUSING: {label} not found at {path}.")
    actual = _sha256_bytes(path.read_bytes())
    if actual != expected:
        raise SystemExit(
            f"REFUSING: {label} sha256 {actual} != pinned {expected} (path: {path})."
        )


# ---------------------------------------------------------------------------
# fetch
# ---------------------------------------------------------------------------


def build_extract(hdi_df: pd.DataFrame, hl_df: pd.DataFrame, gp_df: pd.DataFrame) -> pd.DataFrame:
    """The columns `compute` needs, per plan section 4.1 / spec section 4.1: county and
    year; the five signal scores and raw values; the three dimension scores and names,
    and the composite; the D14 component columns; the county PIT rate_value (as
    `pit_rate`); and the HUD/ACS income columns from geography-profile-series. The last
    two sources contribute only rows whose geography_id is 5 characters (county),
    left-joined on (county, year)."""
    score_and_raw_cols: list[str] = []
    for s in SIGNALS:
        score_and_raw_cols += [s.export_score, s.export_raw]

    keep_cols = ["county_fips", "year"] + score_and_raw_cols + [
        "d1_score", "d2_score", "d3_score", "d1_name", "d2_name", "d3_name",
        COMPOSITE_EXPORT_COL,
        "median_gross_rent_monthly", "median_household_income", "median_sale_price",
    ]
    extract = hdi_df[keep_cols].copy()

    hl = hl_df[hl_df["geography_id"].str.len() == COUNTY_ID_LEN][
        ["geography_id", "year", "rate_value"]
    ].rename(columns={"geography_id": "county_fips", "rate_value": "pit_rate"})
    extract = extract.merge(hl, on=["county_fips", "year"], how="left")

    gp = gp_df[gp_df["geography_id"].str.len() == COUNTY_ID_LEN][
        ["geography_id", "year", "acs_median_household_income", "hud_area_median_income",
         "hud_to_acs_ratio"]
    ].rename(columns={"geography_id": "county_fips"})
    extract = extract.merge(gp, on=["county_fips", "year"], how="left")

    return extract.sort_values(["county_fips", "year"]).reset_index(drop=True)


def fetch(base_url: str = BASE_URL, *, session: Optional[Any] = None,
          layout: Layout = REPO_LAYOUT) -> None:
    getter = session if session is not None else requests

    # Never overwrite the lasting copy: in the deposit folder the extract is the published
    # one, and a rebuild with other library versions can differ byte for byte.
    for existing in (layout.out_dir / EXTRACT_FILENAME, layout.out_dir / EXTRACT_SHA_FILENAME,
                     layout.out_dir / MANIFEST_OUT_FILENAME):
        if existing.exists():
            raise SystemExit(
                f"REFUSING: {existing} already exists. `fetch` does not overwrite the "
                "published extract or manifest; fetch into an empty folder "
                "(--data-dir <new folder>) and compare."
            )

    manifest_url = f"{base_url.rstrip('/')}/{MANIFEST_FILENAME}"
    resp = getter.get(manifest_url, timeout=MANIFEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    manifest_bytes = resp.content
    manifest = json.loads(manifest_bytes)

    run_id = manifest.get("runId")
    if run_id != RUN_ID:
        raise SystemExit(
            f"REFUSING: manifest runId {run_id!r} != pinned {RUN_ID!r}. The public "
            "export has moved since this script's pins were set; do not update the "
            "pin without re-verifying (plan Task 0)."
        )

    files_by_name = {
        f["name"]: f for f in manifest.get("files", []) if isinstance(f, dict)
    }

    downloaded: dict[str, bytes] = {}
    for name, expected_sha in EXPORT_FILE_HASHES.items():
        entry = files_by_name.get(name)
        if entry is None:
            raise SystemExit(f"REFUSING: manifest has no files[] entry named {name!r}.")
        manifest_sha = entry.get("sha256")
        if manifest_sha != expected_sha:
            raise SystemExit(
                f"REFUSING: manifest sha256 for {name} is {manifest_sha!r}, pinned "
                f"{expected_sha!r}."
            )
        file_resp = getter.get(entry["url"], timeout=FILE_TIMEOUT_SECONDS)
        file_resp.raise_for_status()
        payload = file_resp.content
        actual_sha = _sha256_bytes(payload)
        if actual_sha != expected_sha:
            raise SystemExit(
                f"REFUSING: downloaded {name} sha256 {actual_sha} != pinned "
                f"{expected_sha}."
            )
        downloaded[name] = payload
        print(f"[fetch] verified {name}: sha256 {actual_sha} ({len(payload)} bytes)")

    out_dir = layout.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / MANIFEST_OUT_FILENAME).write_bytes(manifest_bytes)
    print(f"[fetch] wrote {out_dir / MANIFEST_OUT_FILENAME} (verbatim bytes)")

    hdi_df = pd.read_parquet(io.BytesIO(downloaded["hdi-scores-county.parquet"]))
    hl_df = pd.read_parquet(io.BytesIO(downloaded["homelessness-landscape.parquet"]))
    gp_df = pd.read_parquet(io.BytesIO(downloaded["geography-profile-series.parquet"]))

    extract = build_extract(hdi_df, hl_df, gp_df)

    extract_path = out_dir / EXTRACT_FILENAME
    extract.to_parquet(extract_path, engine="pyarrow", compression="zstd", index=False)

    extract_sha = _sha256_bytes(extract_path.read_bytes())
    sha_path = out_dir / EXTRACT_SHA_FILENAME
    with open(sha_path, "w", newline="\n", encoding="utf-8") as f:
        f.write(f"{extract_sha}  {EXTRACT_FILENAME}\n")

    print(f"[fetch] wrote {extract_path} ({len(extract)} rows)")
    print(f"[fetch] extract sha256: {extract_sha}")
    if extract_sha != EXTRACT_SHA256:
        # Parquet bytes can differ across pandas/pyarrow versions even when the rows agree.
        print(f"[fetch] WARNING: this differs from the published extract {EXTRACT_SHA256}; "
              "`compute` accepts only the published one.")


# ---------------------------------------------------------------------------
# compute
# ---------------------------------------------------------------------------


def load_v1_json_clips(path: Path = V1_JSON_PATH) -> dict[str, dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"REFUSING: v1 baselines JSON not found at {path}.")
    raw = path.read_bytes()
    actual = _sha256_bytes(raw.replace(b"\r\n", b"\n"))
    if actual != V1_JSON_SHA256_LF:
        raise SystemExit(
            f"REFUSING: v1 baselines JSON sha256 (LF-normalized) {actual} != pinned "
            f"{V1_JSON_SHA256_LF} ({path})."
        )
    data = json.loads(raw.decode("utf-8"))
    out: dict[str, dict[str, Any]] = {}
    for entry in data["baselines"]:
        out[entry["column"]] = {
            "clip_low": float(entry["clip_low"]),
            "clip_high": float(entry["clip_high"]),
            "n": int(entry["n_obs"]),
        }
    return out


def compute_deposit_clips(deposit: pd.DataFrame, v1_json_clips: dict[str, dict[str, Any]]
                           ) -> dict[str, Any]:
    """Table E.1: for each signal, derive clip_low/clip_high from the deposit's own
    county 2010-2019 raw values, assert it reproduces the deposit's own `_norm` column
    within 1e-6, and record the same reproduction error for the v1 JSON clips and the
    paper's printed clips (which are not expected to reproduce -- E-3)."""
    discovery = deposit[
        (deposit["year"] >= DISCOVERY_YEAR_MIN) & (deposit["year"] <= DISCOVERY_YEAR_MAX)
    ]

    result: dict[str, Any] = {}
    for s in SIGNALS:
        lo, hi, n = derive_clips(discovery[s.deposit_raw], s.negate)

        own_norm = normalize(deposit[s.deposit_raw], lo, hi, s.negate)
        err_own = max_abs_error(own_norm, deposit[s.deposit_norm])
        if not (err_own <= 1e-6):
            raise SystemExit(
                f"REFUSING: {s.id} own-derived clips do not reproduce the deposit's "
                f"_norm column (err_own={err_own} > 1e-6). clip_low={lo}, clip_high={hi}."
            )

        printed_lo = round(lo, PRINTED_CLIP_DECIMALS)
        printed_hi = round(hi, PRINTED_CLIP_DECIMALS)
        printed_norm = normalize(deposit[s.deposit_raw], printed_lo, printed_hi, s.negate)
        err_printed = max_abs_error(printed_norm, deposit[s.deposit_norm])
        if not (err_printed <= 1e-6):
            raise SystemExit(
                f"REFUSING: {s.id} clips printed at {PRINTED_CLIP_DECIMALS} decimals do not "
                f"reproduce the deposit's _norm column (err_printed={err_printed} > 1e-6). "
                f"clip_low={printed_lo}, clip_high={printed_hi}."
            )

        v1 = v1_json_clips.get(s.v1_json_column)
        if v1 is not None:
            v1_norm = normalize(deposit[s.deposit_raw], v1["clip_low"], v1["clip_high"], s.negate)
            err_v1_json = max_abs_error(v1_norm, deposit[s.deposit_norm])
        else:
            err_v1_json = None

        paper = PAPER_PRINTED_CLIPS.get(s.id)
        if paper is not None:
            paper_norm = normalize(
                deposit[s.deposit_raw], paper["clip_low"], paper["clip_high"], s.negate
            )
            err_paper_table = max_abs_error(paper_norm, deposit[s.deposit_norm])
        else:
            err_paper_table = None

        result[s.id] = {
            "label": s.label,
            "clip_low": lo,
            "clip_high": hi,
            "n": n,
            "err_own": err_own,
            "printed_clip_low": printed_lo,
            "printed_clip_high": printed_hi,
            "printed_decimals": PRINTED_CLIP_DECIMALS,
            "err_printed": err_printed,
            "err_v1_json": err_v1_json,
            "err_paper_table": err_paper_table,
            "v1_json_clip_low": v1["clip_low"] if v1 else None,
            "v1_json_clip_high": v1["clip_high"] if v1 else None,
            "v1_json_n": v1["n"] if v1 else None,
            "paper_table_clip_low": paper["clip_low"] if paper else None,
            "paper_table_clip_high": paper["clip_high"] if paper else None,
            "paper_table_n": paper["n"] if paper else None,
        }
    return result


def compute_national_supporting_clips(national: pd.DataFrame) -> dict[str, Any]:
    """The paper's printed clip table (P04:293-297) is derived from the deposit's
    supporting national file, on county rows, 2010-2019, non-null raw (vacancy
    negated), p1/p99 -- the same rule as `compute_deposit_clips`, applied to the
    supporting file instead of the primary one. That file carries no severe-cost-burden
    column, so the severe row is reported as not derivable from it (consistent with the
    paper's own footnote, P04:299-302, that the severe clip was independently verified
    rather than sourced from the same discovery run as the other four)."""
    county = national[national["geo_level"] == "county"]
    discovery = county[
        (county["year"] >= DISCOVERY_YEAR_MIN) & (county["year"] <= DISCOVERY_YEAR_MAX)
    ]

    result: dict[str, Any] = {}
    for s in SIGNALS:
        col = s.deposit_raw
        paper = PAPER_PRINTED_CLIPS.get(s.id)
        if col not in national.columns:
            result[s.id] = {
                "label": s.label,
                "clip_low": None,
                "clip_high": None,
                "n": None,
                "max_abs_diff_from_paper_printed": None,
                "note": (
                    f"{col} is not a column in the national supporting file; the "
                    "severe-cost-burden signal postdates that discovery run (E-3)."
                ),
            }
            continue

        lo, hi, n = derive_clips(discovery[col], s.negate)
        if paper is not None:
            diff = max(abs(lo - paper["clip_low"]), abs(hi - paper["clip_high"]))
            # E-3 attributes the printed row to this file: it must match to the printed
            # six decimals (half a unit in the sixth place) and on n.
            if diff > 5e-7 or n != paper["n"]:
                raise SystemExit(
                    f"REFUSING: {s.id}: the national file's clips (n={n}) do not match "
                    f"the paper's printed row (n={paper['n']}) to six decimals "
                    f"(max diff {diff:.3g}); E-3's attribution would not hold."
                )
        else:
            diff = None
        result[s.id] = {
            "label": s.label,
            "clip_low": lo,
            "clip_high": hi,
            "n": n,
            "max_abs_diff_from_paper_printed": diff,
        }
    return result


def compute_table(deposit: pd.DataFrame, extract: pd.DataFrame) -> dict[str, Any]:
    """Table E.3 (spec section 4.3): columns B and C of the bivariate R^2 chain over
    the common universe, plus C on the export's own universe, plus Spearman rho for
    the composite."""
    check_dimension_names(extract)

    deposit_complete_holdout_n = int(
        len(deposit[
            (deposit["completeness_class"] == "complete") & deposit["year"].isin(HOLDOUT_YEARS)
        ])
    )

    common = common_universe(deposit, extract, "pit_rate", HOLDOUT_YEARS)
    own = export_own_universe(extract, "pit_rate", HOLDOUT_YEARS)

    y_common = common["pit_rate"]
    y_own = own["pit_rate"]

    measures: dict[str, Any] = {}

    for s in SIGNALS:
        b_r2, b_n = bivariate_r2(common[s.deposit_norm], y_common)
        c_r2, c_n = bivariate_r2(common[s.export_score], y_common)
        c_own_r2, c_own_n = bivariate_r2(own[s.export_score], y_own)
        measures[s.id] = {
            "level": "signal", "label": s.label,
            "b_r2": b_r2, "b_n": b_n,
            "c_r2": c_r2, "c_n": c_n,
            "c_own_r2": c_own_r2, "c_own_n": c_own_n,
        }

    for d in DIMENSIONS:
        b_r2, b_n = bivariate_r2(common[d.deposit_col], y_common)
        c_r2, c_n = bivariate_r2(common[d.export_col], y_common)
        c_own_r2, c_own_n = bivariate_r2(own[d.export_col], y_own)
        measures[d.id] = {
            "level": "dimension", "label": d.label,
            "b_r2": b_r2, "b_n": b_n,
            "c_r2": c_r2, "c_n": c_n,
            "c_own_r2": c_own_r2, "c_own_n": c_own_n,
        }

    b_r2, b_n = bivariate_r2(common[COMPOSITE_DEPOSIT_COL], y_common)
    c_r2, c_n = bivariate_r2(common[COMPOSITE_EXPORT_COL], y_common)
    c_own_r2, c_own_n = bivariate_r2(own[COMPOSITE_EXPORT_COL], y_own)
    measures["composite"] = {
        "level": "composite", "label": "equal-thirds",
        "b_r2": b_r2, "b_n": b_n,
        "c_r2": c_r2, "c_n": c_n,
        "c_own_r2": c_own_r2, "c_own_n": c_own_n,
    }

    mask_b = common[COMPOSITE_DEPOSIT_COL].notna() & y_common.notna()
    rho_b, p_b = spearmanr(common.loc[mask_b, COMPOSITE_DEPOSIT_COL], y_common[mask_b])
    mask_c = common[COMPOSITE_EXPORT_COL].notna() & y_common.notna()
    rho_c, p_c = spearmanr(common.loc[mask_c, COMPOSITE_EXPORT_COL], y_common[mask_c])

    return {
        "run_id": RUN_ID,
        "deposit_sha256": DEPOSIT_SHA256,
        "export_hashes": dict(EXPORT_FILE_HASHES),
        "deposit_complete_holdout_n": deposit_complete_holdout_n,
        "common_universe_n": int(len(common)),
        "export_own_universe_n": int(len(own)),
        "measures": measures,
        "spearman_composite_b": {"rho": float(rho_b), "p": float(p_b), "n": int(mask_b.sum())},
        "spearman_composite_c": {"rho": float(rho_c), "p": float(p_c), "n": int(mask_c.sum())},
        "column_a_v1_printed": V1_PRINTED_TABLE_6_2,
    }


def compute_facts(deposit: pd.DataFrame, extract: pd.DataFrame, national: pd.DataFrame
                   ) -> dict[str, Any]:
    """facts.json: every number the erratum's prose cites from these inputs (plan
    section 4.1 / spec section 4.1)."""
    king_dep = deposit[(deposit["geo_id"] == KING_COUNTY_FIPS) & (deposit["year"] == KING_COUNTY_YEAR)]
    king_exp = extract[
        (extract["county_fips"] == KING_COUNTY_FIPS) & (extract["year"] == KING_COUNTY_YEAR)
    ]
    if len(king_dep) != 1 or len(king_exp) != 1:
        raise SystemExit(
            f"REFUSING: King County {KING_COUNTY_FIPS} {KING_COUNTY_YEAR} did not match "
            f"exactly one row in deposit ({len(king_dep)}) or extract ({len(king_exp)})."
        )
    king_dep_row = king_dep.iloc[0]
    king_exp_row = king_exp.iloc[0]

    deposit_rent = float(king_dep_row["sig_rent_to_income_acs_raw"])
    deposit_price = float(king_dep_row["sig_price_to_income_raw"])
    export_rent = float(king_exp_row["rent_to_income_raw_value"])
    export_price = float(king_exp_row["price_to_income_raw_value"])
    median_gross_rent_monthly = float(king_exp_row["median_gross_rent_monthly"])
    median_household_income = float(king_exp_row["median_household_income"])
    median_sale_price = float(king_exp_row["median_sale_price"])
    hud_area_median_income = float(king_exp_row["hud_area_median_income"])

    implied_rent_denominator = 12.0 * median_gross_rent_monthly / deposit_rent
    if round(implied_rent_denominator) != KING_COUNTY_ACS_RENTER_MEDIAN_2024:
        raise SystemExit(
            f"REFUSING: King County {KING_COUNTY_YEAR}: the deposit's implied rent "
            f"denominator {implied_rent_denominator:.2f} does not round to the ACS renter "
            f"median {KING_COUNTY_ACS_RENTER_MEDIAN_2024} (E-1)."
        )
    price_check_hud_ami = round(median_sale_price / hud_area_median_income, 4)

    king_county_facts = {
        "geography_id": KING_COUNTY_FIPS,
        "year": KING_COUNTY_YEAR,
        "deposit_rent_to_income_raw": deposit_rent,
        "deposit_price_to_income_raw": deposit_price,
        "export_rent_to_income_raw_value": export_rent,
        "export_price_to_income_raw_value": export_price,
        "median_gross_rent_monthly": median_gross_rent_monthly,
        "median_household_income": median_household_income,
        "median_sale_price": median_sale_price,
        "hud_area_median_income": hud_area_median_income,
        "deposit_implied_rent_denominator": implied_rent_denominator,
        "acs_renter_median_income_b25119_003e": KING_COUNTY_ACS_RENTER_MEDIAN_2024,
        "price_check_median_sale_price_over_hud_ami": price_check_hud_ami,
        "price_check_matches_deposit_price_to_income_raw_4dp": bool(
            price_check_hud_ami == round(deposit_price, 4)
        ),
    }

    ratio_col = "hud_to_acs_ratio"
    hud_window = extract[
        (extract["year"] >= HUD_RATIO_YEAR_MIN) & (extract["year"] <= HUD_RATIO_YEAR_MAX)
        & extract[ratio_col].notna()
    ][ratio_col]
    hud_to_acs_ratio_facts = {
        "n": int(len(hud_window)),
        "share_above_1": float((hud_window > 1).mean()),
        "median": float(hud_window.median()),
        "p25": float(hud_window.quantile(0.25)),
        "p75": float(hud_window.quantile(0.75)),
    }

    dep_vac = deposit[["geo_id", "year", "sig_rental_vacancy_rate_raw"]].rename(
        columns={"geo_id": "county_fips"}
    )
    exp_vac = extract[["county_fips", "year", "rental_vacancy_rate_raw_value"]]
    vac_merged = dep_vac.merge(exp_vac, on=["county_fips", "year"], how="inner")
    vac_merged = vac_merged.dropna(
        subset=["sig_rental_vacancy_rate_raw", "rental_vacancy_rate_raw_value"]
    )
    vac_diff = vac_merged["rental_vacancy_rate_raw_value"] - vac_merged["sig_rental_vacancy_rate_raw"]
    vacancy_raw_change = {"mean": float(vac_diff.mean()), "n": int(len(vac_diff))}

    national_clips = compute_national_supporting_clips(national)
    king_national = national[
        (national["geo_level"] == "county")
        & (national["geo_id"] == KING_COUNTY_FIPS)
        & (national["year"] == KING_COUNTY_YEAR)
    ]
    king_national_price = (
        float(king_national["sig_price_to_income_raw"].iloc[0]) if len(king_national) else None
    )

    return {
        "king_county_53033_2024": king_county_facts,
        "hud_to_acs_ratio_2010_2024": hud_to_acs_ratio_facts,
        "vacancy_raw_change_export_minus_deposit": vacancy_raw_change,
        "national_supporting_file": {
            "path": NATIONAL_SUPPORTING_RECORD_PATH,
            "sha256": NATIONAL_SUPPORTING_SHA256,
            "king_county_53033_2024_price_to_income_raw": king_national_price,
            "clips": national_clips,
        },
    }


def _fmt_r2(value: float) -> str:
    return "nan" if (isinstance(value, float) and math.isnan(value)) else f"{value:.4f}"


def write_county_table_txt(path: Path, table: dict[str, Any]) -> None:
    order = [s.id for s in SIGNALS] + [d.id for d in DIMENSIONS] + ["composite"]
    a_key_map = {
        "price_to_income": "price_to_income",
        "rent_to_income": "rent_to_income",
        "cost_burdened_share": "cost_burdened_share",
        "severe_cost_burdened_share": "severe_cost_burdened_share",
        "rental_vacancy_rate": "rental_vacancy_rate",
        "affordability": "affordability_dim",
        "cost_burden": "cost_burden_dim",
        "availability": "availability_dim",
        "composite": "composite",
    }
    v1 = table["column_a_v1_printed"]

    lines: list[str] = []
    lines.append(f"County table (Table 6.2 recomputation) -- export run {table['run_id']}")
    lines.append("")
    lines.append(f"deposit complete county-years, 2022-2024:     {table['deposit_complete_holdout_n']}")
    lines.append(f"common universe (columns B and C):            {table['common_universe_n']}")
    lines.append(f"export-own universe (C, secondary line):      {table['export_own_universe_n']}")
    lines.append("")

    header = (
        f"{'Level':<10} {'Measure':<45} {'A':>7} {'B':>7} {'C':>7} {'n(B/C)':>8}  "
        f"{'C-own':>7} {'n(own)':>8}"
    )
    lines.append(header)
    lines.append("-" * len(header))
    for key in order:
        m = table["measures"][key]
        a_val = v1.get(a_key_map[key], {}).get("printed", "--")
        lines.append(
            f"{m['level']:<10} {m['label']:<45} {a_val:>7} "
            f"{_fmt_r2(m['b_r2']):>7} {_fmt_r2(m['c_r2']):>7} {m['b_n']:>8}  "
            f"{_fmt_r2(m['c_own_r2']):>7} {m['c_own_n']:>8}"
        )
    lines.append("")

    sb = table["spearman_composite_b"]
    sc = table["spearman_composite_c"]
    lines.append(f"Spearman rho, composite B (deposit) vs pit_rate: {sb['rho']:.4f}  n={sb['n']}")
    lines.append(f"Spearman rho, composite C (export)  vs pit_rate: {sc['rho']:.4f}  n={sc['n']}")
    lines.append("")
    lines.append(
        f"Column A: v1.0 as printed (P06:224-234), n={v1['n']} "
        "(June 2026 SQL outcome series, not public -- E-10)."
    )
    lines.append("Column B: deposit score vs export 2.0 pit_rate, common universe.")
    lines.append("Column C: export 2.0 score vs export 2.0 pit_rate, common universe.")
    lines.append(
        "C-own: column C on the export's own analogue of 'complete' "
        "(all five signal scores present), not the common universe."
    )

    text = "\n".join(lines) + "\n"
    with open(path, "w", newline="\n", encoding="utf-8") as f:
        f.write(text)


def compute(layout: Layout = REPO_LAYOUT) -> None:
    _verify_file_sha256(layout.deposit, DEPOSIT_SHA256, "deposit parquet")
    _verify_file_sha256(
        layout.national, NATIONAL_SUPPORTING_SHA256,
        "national supporting parquet",
    )

    out_dir = layout.out_dir
    extract_path = out_dir / EXTRACT_FILENAME
    sha_path = out_dir / EXTRACT_SHA_FILENAME
    if not extract_path.exists() or not sha_path.exists():
        raise SystemExit(
            f"REFUSING: {extract_path} or {sha_path} is missing -- run the 'fetch' "
            "subcommand first."
        )
    recorded_extract_sha = sha_path.read_text(encoding="utf-8").strip().split()[0]
    if recorded_extract_sha != EXTRACT_SHA256:
        raise SystemExit(
            f"REFUSING: {sha_path} records {recorded_extract_sha}, not the published "
            f"extract's {EXTRACT_SHA256}."
        )
    _verify_file_sha256(extract_path, EXTRACT_SHA256, "export extract parquet")

    deposit = pd.read_parquet(layout.deposit)
    deposit = deposit[deposit["geo_level"] == "county"].copy()
    deposit["geo_id"] = deposit["geo_id"].astype(str)

    extract = pd.read_parquet(extract_path)

    national = pd.read_parquet(layout.national)
    national["geo_id"] = national["geo_id"].astype(str)

    v1_json_clips = load_v1_json_clips(layout.v1_json)

    deposit_clips = compute_deposit_clips(deposit, v1_json_clips)
    table = compute_table(deposit, extract)
    facts = compute_facts(deposit, extract, national)

    write_json(
        out_dir / "deposit-clips.json", deposit_clips,
        full_precision_keys=FULL_PRECISION_KEYS,
    )
    write_json(out_dir / "county-table.json", table)
    write_json(out_dir / "facts.json", facts)
    write_county_table_txt(out_dir / "county-table.txt", table)

    print("[compute] wrote deposit-clips.json, county-table.json, county-table.txt, facts.json")
    print(f"[compute] deposit complete 2022-2024: {table['deposit_complete_holdout_n']}")
    print(f"[compute] common universe:            {table['common_universe_n']}")
    print(f"[compute] export-own universe:        {table['export_own_universe_n']}")
    for s in SIGNALS:
        c = deposit_clips[s.id]
        print(f"[compute] {s.id}: err_own={c['err_own']:.3e} err_printed={c['err_printed']:.3e}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    data_dir_help = (
        "read every input from, and write every output to, this one folder (the data "
        "deposit's layout) instead of the repository's paths"
    )
    for name, help_text in (
        ("fetch", "download and verify the export extract"),
        ("compute", "recompute the clip table, county table and facts"),
    ):
        sp = sub.add_parser(name, help=help_text)
        sp.add_argument("--data-dir", type=Path, default=None, help=data_dir_help)
    args = parser.parse_args()

    layout = flat_layout(args.data_dir.resolve()) if args.data_dir else REPO_LAYOUT
    if args.command == "fetch":
        fetch(layout=layout)
    elif args.command == "compute":
        compute(layout)


if __name__ == "__main__":
    main()
