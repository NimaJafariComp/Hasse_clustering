# `newAlgV4.py` Guide

## Purpose

`newAlgV4.py` analyzes event sequences and builds ordering matrices for a user-selected set of event IDs.

In the most general form, you choose a set of `n` event IDs based on your clustering or Hasse-diagram analysis, and the algorithm builds an `n x n` ordering matrix over that set.

In the current script instance, the chosen event set is:

- `e3`
- `e4`
- `e5`
- `e6`

In this script, the goal is to learn whether one event always happens before another across a set of sequences.

It does two main things:

1. builds one matrix per input sequence
2. builds one consensus matrix across all sequences

So if you feed `k` sequences into the algorithm:

- you get `k` per-sequence matrices `M_c`
- and one final consensus matrix `M`

It also saves the non-empty per-sequence matrices to a JSON file.

## Input

The script reads:

- [plant_events_summary.csv](/Users/nimajafari/Programming/research/vision-Ai/figure_skating/new%20way/clustering/plant_events_summary.csv:1)

It expects that CSV to contain a `sequence` column where each row is a Python-style list, for example:

```python
["e3", "e5", "e6"]
```

The script parses each row with `ast.literal_eval(...)`.

It also optionally uses the `name` column, if present, just for printing readable identifiers next to matrices.

## Event Set And Order Used

The general idea is:

- choose any event set you care about
- fix one consistent order for those events
- build matrices using that order

So if your selected set has `n` events, the algorithm produces an `n x n` matrix.

In the current script, the event order is fixed as:

```text
[e3, e4, e5, e6]
```

That means:

- row 0 / column 0 = `e3`
- row 1 / column 1 = `e4`
- row 2 / column 2 = `e5`
- row 3 / column 3 = `e6`

This means the current implementation is a `4 x 4` special case of the more general `n x n` method.

## What `method1` Does

`method1(c_list, names=None)` processes each sequence independently.

For each sequence `c`, it builds:

### 1. A position dictionary `P`

For each selected event, it stores the set of positions where that event appears.

Example idea:

```python
P = {
  "e3": {1},
  "e4": {3},
  "e5": {2},
  "e6": set()
}
```

### 2. A per-sequence matrix `M_c`

`M_c[i][j] = 1` if event `i` is definitely before event `j` in that sequence.

The exact rule is:

```text
max(P_i) < min(P_j)
```

So event `i` must finish appearing before event `j` ever appears.

This is a strict ordering rule.

### Meaning of `M_c`

If:

```text
M_c[0][2] = 1
```

then:

```text
e3 happens before e5 in that sequence
```

If it is `0`, the script is not willing to claim that strict ordering from that sequence.

### Important Clarification

For every input sequence, the algorithm produces a corresponding per-sequence matrix.

So if your CSV has 100 rows, `method1(...)` conceptually produces 100 sequence-level matrices:

```text
M_c^(1), M_c^(2), ..., M_c^(100)
```

Some of those matrices may be all zeros if that sequence does not contain enough evidence for any strict ordering.

## What `method2ForProcessed` Does

`method2ForProcessed(processed)` builds one consensus matrix `M` across all processed sequences.

This is the main summary matrix.

For every pair `(ei, ej)`, it sets:

```text
M[i][j] = 1
```

only if both conditions are true.

### Condition A

For every sequence where both `ei` and `ej` appear, that sequence must agree that `ei` is before `ej`.

In other words:

- if both events are present
- there must be no contradiction

### Condition B

There must be at least one sequence where both events appear and `ei` is strictly before `ej`.

This avoids putting a `1` in the matrix just because there was no contradiction but also no actual evidence.

### Meaning of the final consensus matrix `M`

`M[i][j] = 1` means:

- across all relevant sequences, there is no contradiction to `ei` being before `ej`
- and there is at least one sequence giving positive evidence that `ei` is before `ej`

So `M` is a conservative consensus ordering matrix.

## What Matrix Gets Generated

The main final matrix is:

```text
M
```

In general, it is an `n x n` binary matrix over the selected event set.

In the current script, it is a `4 x 4` binary matrix over:

```text
[e3, e4, e5, e6]
```

### Interpretation

- `1` means the row event is supported as happening before the column event
- `0` means that ordering is not established

### Diagonal

Inside `method2ForProcessed`, the diagonal is left as `0`.

So by default:

```text
M[i][i] = 0
```

That makes sense because the matrix is about ordering between different events.

## JSON Output Saved

The script also saves selected per-sequence matrices to:

- [M_c_matrices_diagonal_1 ('e3', 'e4', 'e5', 'e6').json](/Users/nimajafari/Programming/research/vision-Ai/figure_skating/new%20way/clustering/M_c_matrices_diagonal_1%20('e3',%20'e4',%20'e5',%20'e6').json)

Only sequences with a non-empty matrix are saved.

For those saved matrices:

- the diagonal is manually changed to `1`
- the event-position sets `P` are converted to sorted lists so they can be written as JSON

Each JSON record contains:

- `name`
- `M_c`
- `P`

## How To Run

From the project root:

```bash
python3 clustering/newAlgV4.py
```

## What It Prints

When you run it, it:

1. reads the CSV
2. builds and prints non-empty `M_c` matrices
3. prints how many non-empty per-sequence matrices it found
4. prints the final consensus matrix `M`
5. saves the selected `M_c` matrices and their `P` dictionaries to JSON

## Important Notes

### 1. The method is general, but the current script configuration is specific

The algorithm itself can work with any user-selected event set.

But this particular script file is currently hard-coded to:

- `e3`
- `e4`
- `e5`
- `e6`

So even if your CSV contains other event IDs, this current version ignores them unless you change the selected event list in the code.

This is useful when you want to focus on only the events that matter for a given clustering task or Hasse-diagram construction.

### 2. Ordering is strict

It does not say "`ei` tends to come before `ej`."

It only marks `1` when the sequence evidence supports a strict non-overlapping before-relation.

### 3. Repeated events are allowed

That is why the script stores sets of positions in `P` and uses:

- `max(P_i)`
- `min(P_j)`

This handles repeated appearances of the same event.

## Short Summary

`newAlgV4.py` is a strict event-ordering algorithm. In general, you choose any set of `n` event IDs, and it builds an `n x n` matrix describing which events are consistently supported as happening before others. In the current script, that general method is instantiated on the four-event set `e3/e4/e5/e6`, producing per-sequence matrices and one final conservative consensus matrix.
