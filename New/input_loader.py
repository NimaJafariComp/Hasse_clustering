"""
Input parsing helpers for Hasse Sequence Clustering.

Accepted formats:
- JSON: a list of sequences, e.g. [["e1", "e2"], ["e2", "e5"]]
- CSV: a table with a sequence column whose values are Python/JSON-style lists,
  e.g. "['e1', 'e2', 'e5']"
"""

from __future__ import annotations

import ast
import csv
import io
import json


def _validate_sequences(sequences):
    if not isinstance(sequences, list):
        raise ValueError("input must be a list of sequences")
    out = []
    for idx, seq in enumerate(sequences, 1):
        if not isinstance(seq, list):
            raise ValueError(f"sequence #{idx} is not a list")
        out.append([str(item) for item in seq])
    return out


def parse_json_sequences(text: str):
    """Parse a JSON list of sequences."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid JSON: {e}") from e
    return _validate_sequences(data)


def parse_csv_sequences(text: str, sequence_column: str = "sequence"):
    """Parse CSV rows with a Python/JSON-style sequence cell."""
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV has no header row")
    if sequence_column not in reader.fieldnames:
        columns = ", ".join(reader.fieldnames)
        raise ValueError(
            f"CSV must contain a {sequence_column!r} column; found: {columns}"
        )

    sequences = []
    for row_idx, row in enumerate(reader, 2):
        raw = (row.get(sequence_column) or "").strip()
        if not raw:
            continue
        try:
            seq = ast.literal_eval(raw)
        except (SyntaxError, ValueError) as e:
            raise ValueError(
                f"row {row_idx}: could not parse {sequence_column!r} as a list"
            ) from e
        if not isinstance(seq, list):
            raise ValueError(f"row {row_idx}: {sequence_column!r} is not a list")
        sequences.append([str(item) for item in seq])
    return sequences


def parse_sequences_text(text: str, input_format: str = "auto",
                         sequence_column: str = "sequence"):
    """Parse sequences from text using JSON, CSV, or auto-detection."""
    raw = text.strip()
    if not raw:
        raise ValueError("input is empty")

    fmt = (input_format or "auto").lower()
    if fmt == "json":
        return parse_json_sequences(raw)
    if fmt == "csv":
        return parse_csv_sequences(raw, sequence_column=sequence_column)
    if fmt != "auto":
        raise ValueError("input_format must be one of: auto, json, csv")

    if raw[0] in "[{":
        try:
            return parse_json_sequences(raw)
        except ValueError:
            pass
    return parse_csv_sequences(raw, sequence_column=sequence_column)
