import ast
import pandas as pd
import os
from collections import defaultdict


script_dir = os.path.dirname(os.path.abspath(__file__))

# Locate input CSV: try common names first, then fall back to any synth*.csv
_candidates = [
    "plant_events_summary.csv",
    "synth.events.csv",
    "synth-events.csv",
    "synth_events.csv",
    "synth-data.csv",
    "synth.csv",
]
CSV_FILE = None

# Search in a few likely locations (script dir, sibling skatingV115 outputs, project-level folders)
search_bases = [
    script_dir,
    os.path.join(script_dir, "..", "skatingV115", "sequence_csv_outputs"),
    os.path.join(script_dir, "..", "sequence_csv_outputs"),
    os.path.join(script_dir, "..", "..", "figure_skating", "skatingV115", "sequence_csv_outputs"),
]
for base in search_bases:
    for _c in _candidates:
        _p = os.path.join(base, _c)
        if os.path.exists(_p):
            CSV_FILE = _p
            break
    if CSV_FILE:
        break

# final fallback: search recursively for synth*.csv or plant_events_summary.csv
if CSV_FILE is None:
    import glob as _g
    matches = sorted(_g.glob(os.path.join(script_dir, "**", "synth*.csv"), recursive=True))
    if not matches:
        matches = sorted(_g.glob(os.path.join(script_dir, "**", "plant_events_summary.csv"), recursive=True))
    if matches:
        CSV_FILE = matches[0]

if CSV_FILE is None:
    raise FileNotFoundError(
        f"No input CSV found in {script_dir}. Looked for: {', '.join(_candidates)} or pattern 'synth*.csv'"
    )
print(f"Using input CSV: {CSV_FILE}")

import argparse
import json
import numpy as np

OUTPUT_FILE = os.path.join(script_dir, "event_pair_ordering_ratios.csv")
LABEL_COLUMN = "label"  # legacy: contains "won" or "lost"

# --- CLI ---
parser = argparse.ArgumentParser(description="Compute event ordering statistics across dive groups")
parser.add_argument("--csv", help="Path to synth CSV (overrides auto-detection)", default=None)
parser.add_argument("--group-col", help="Column to group dives by (default: 'dive_group' if present, else 'label')", default=None)
parser.add_argument("--alpha", type=float, default=0.0, help="Laplace smoothing (additive) to avoid zeros")
parser.add_argument("--out", default=OUTPUT_FILE, help="Output CSV path")
parser.add_argument("--exclude-prefixes", default="e11,e81", help="Comma-separated event code prefixes to ignore (e.g., 'e7,e10')")
args = parser.parse_args()
if args.csv:
    CSV_FILE = args.csv
OUTPUT_FILE = args.out
ALPHA = float(args.alpha)
EXCLUDE_PREFIXES = [p.strip() for p in args.exclude_prefixes.split(',') if p.strip()]
print(f"Excluding event prefixes: {EXCLUDE_PREFIXES}")


def parse_sequence(seq_str):
    try:
        parsed = ast.literal_eval(seq_str)
        return parsed if isinstance(parsed, list) else []
    except:
        return []

# build full event set from both data
def extract_event_set(df):
    event_set = set()
    for s in df["sequence"]:
        parsed = parse_sequence(s)
        for t in parsed:
            elements = list(t) if isinstance(t, tuple) else [t]
            event_set.update(elements)
    return event_set

# identify win/loss
def is_winning_episode(seq_str):
    parsed = parse_sequence(seq_str)
    if not parsed:
        return False
    last_term = parsed[-1]
    last_events = list(last_term) if isinstance(last_term, tuple) else [last_term]
    return any(e in last_events for e in ["e9", "e12"])

# check if e_i occurs before e_j in a sequence
def occurs_before(seq, e_i, e_j):
    seen_i, seen_j = None, None
    for idx, term in enumerate(seq):
        elements = list(term) if isinstance(term, tuple) else [term]
        if e_i in elements and seen_i is None:
            seen_i = idx
        if e_j in elements and seen_j is None:
            seen_j = idx
    return (seen_i is not None and seen_j is not None and seen_i < seen_j)


df_all = pd.read_csv(CSV_FILE)

# Determine grouping column (figure-skating friendly defaults)
if args.group_col:
    GROUP_COL = args.group_col
elif "toe_jump_type" in df_all.columns:
    GROUP_COL = "toe_jump_type"
elif "takeoff_foot" in df_all.columns:
    GROUP_COL = "takeoff_foot"
elif "dive_group" in df_all.columns:
    GROUP_COL = "dive_group"
elif LABEL_COLUMN in df_all.columns:
    GROUP_COL = LABEL_COLUMN
elif "name" in df_all.columns:
    GROUP_COL = "name"
else:
    # try to infer useful groupings from a 'tokens' column (look for toe_jump_type or dive_group)
    inferred = None
    if "tokens" in df_all.columns:
        def _extract_group(tokstr):
            if not isinstance(tokstr, str):
                return None
            for t in tokstr.split():
                if t.startswith("toe_jump_type:"):
                    return t.split(":", 1)[1]
            for t in tokstr.split():
                if t.startswith("dive_group:"):
                    return t.split(":", 1)[1]
            return None
        df_all["inferred_group"] = df_all["tokens"].apply(_extract_group)
        if df_all["inferred_group"].notna().any():
            inferred = "inferred_group"

    if inferred is None:
        raise ValueError("No grouping column found (provide --group-col or include 'toe_jump_type'/'takeoff_foot'/'name' or 'label'); tried to infer from 'tokens' column but failed")
    GROUP_COL = inferred
    print(f"Inferred grouping column '{GROUP_COL}' from 'tokens' column")

print(f"Grouping dives by column: {GROUP_COL}")

# Build event vocabulary
X = sorted(list(extract_event_set(df_all)))
m = len(X)
event_index = {e: i for i, e in enumerate(X)}

# count occurrences per group
group_counts = {g: defaultdict(int) for g in sorted(df_all[GROUP_COL].dropna().unique())}
group_totals = {g: 0 for g in group_counts}

def count_orderings_into(df, counter_dict, totals_dict):
    for idx, row in df.iterrows():
        seq = parse_sequence(row["sequence"])
        g = row[GROUP_COL]
        totals_dict[g] += 1
        for i in range(m):
            for j in range(m):
                if i != j and occurs_before(seq, X[i], X[j]):
                    counter_dict[g][(i, j)] += 1

count_orderings_into(df_all, group_counts, group_totals)

# compute per-pair, per-group fractions and discrimination metrics
records = []
groups = sorted(group_counts.keys())
for i in range(m):
    for j in range(m):
        if i == j:
            continue
        # skip pairs involving excluded event prefixes (e.g., somersaults/twist/group tokens)
        if any(X[i].startswith(pref) for pref in EXCLUDE_PREFIXES) or any(X[j].startswith(pref) for pref in EXCLUDE_PREFIXES):
            continue
        p_by_group = {}
        for g in groups:
            tot = group_totals[g]
            cnt = group_counts[g].get((i, j), 0)
            # smoothing
            p = (cnt + ALPHA) / (tot + ALPHA * 1.0) if tot else 0.0
            p_by_group[g] = float(p)

        p_vals = list(p_by_group.values())
        p_max = max(p_vals)
        p_min = min(p_vals)
        g_max = max(p_by_group, key=p_by_group.get)
        g_min = min(p_by_group, key=p_by_group.get)
        ratio = float('inf') if p_min == 0 and p_max > 0 else (p_max / p_min if p_min > 0 else 0.0)
        spread = p_max - p_min
        var = float(np.var(p_vals))

        records.append({
            "i": X[i],
            "j": X[j],
            "p_max_group": g_max,
            "p_max": round(p_max, 4),
            "p_min_group": g_min,
            "p_min": round(p_min, 4),
            "ratio": ratio,
            "spread": round(spread, 4),
            "var": round(var, 6),
            "per_group": json.dumps(p_by_group)
        })

# sort by ratio (desc), then spread
df_result = pd.DataFrame(records).sort_values(by=["ratio", "spread"], ascending=[False, False])
df_result.to_csv(OUTPUT_FILE, index=False)

print(f"Saved discriminative ordering table to: {OUTPUT_FILE}")
print(df_result.head(10))

# ----------------- per-event association (Cramer's V) -----------------
def _chi2_from_table(obs):
    # obs: list of [present, absent] per group
    import math
    obs = [[float(x) for x in row] for row in obs]
    rows = len(obs)
    cols = 2
    n = sum(sum(r) for r in obs)
    if n == 0:
        return 0.0, 0
    row_sums = [sum(r) for r in obs]
    col_sums = [sum(obs[r][c] for r in range(rows)) for c in range(cols)]
    chi2 = 0.0
    for r in range(rows):
        for c in range(cols):
            exp = row_sums[r] * col_sums[c] / n
            if exp > 0:
                chi2 += (obs[r][c] - exp) ** 2 / exp
    df = (rows - 1) * (cols - 1)
    return chi2, df

# build per-event association table
event_records = []
groups = sorted(group_counts.keys())
N = len(df_all)
for e in X:
    # skip excluded prefixes
    if any(e.startswith(pref) for pref in EXCLUDE_PREFIXES):
        continue
    # per-group counts
    pres_by_group = {g: 0 for g in groups}
    tot_by_group = {g: 0 for g in groups}
    for idx, row in df_all.iterrows():
        g = row[GROUP_COL]
        tot_by_group[g] += 1
        seq = parse_sequence(row["sequence"])
        present = False
        for term in seq:
            elements = list(term) if isinstance(term, tuple) else [term]
            if e in elements:
                present = True
                break
        if present:
            pres_by_group[g] += 1
    obs = [[pres_by_group[g], tot_by_group[g] - pres_by_group[g]] for g in groups]
    chi2, df = _chi2_from_table(obs)
    if N == 0:
        cramers_v = 0.0
    else:
        k = min(len(groups) - 1, 1) if len(groups) > 1 else 0
        cramers_v = (chi2 / (N * k)) ** 0.5 if k > 0 else 0.0
    p_by_group = {g: (pres_by_group[g] / tot_by_group[g] if tot_by_group[g] else 0.0) for g in groups}
    p_vals = list(p_by_group.values())
    p_max = max(p_vals)
    p_min = min(p_vals)
    g_max = max(p_by_group, key=p_by_group.get)
    g_min = min(p_by_group, key=p_by_group.get)
    spread = p_max - p_min
    event_records.append({
        "event": e,
        "cramers_v": round(cramers_v, 4),
        "p_max_group": g_max,
        "p_max": round(p_max, 4),
        "p_min_group": g_min,
        "p_min": round(p_min, 4),
        "spread": round(spread, 4),
        "per_group": json.dumps(p_by_group)
    })

EVENT_OUT = os.path.join(script_dir, "event_associations.csv")
pd.DataFrame(event_records).sort_values(by=["cramers_v", "spread"], ascending=[False, False]).to_csv(EVENT_OUT, index=False)
print(f"Saved per-event association table to: {EVENT_OUT}")
print(pd.DataFrame(event_records).sort_values(by=["cramers_v", "spread"], ascending=[False, False]).head(20))
