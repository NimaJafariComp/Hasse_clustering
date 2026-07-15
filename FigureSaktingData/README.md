# Figure Skating Data: Why We Could Not Reliably Go Beyond `r = 4`

This note explains why the figure skating experiments become computationally
expensive as soon as we increase the maximum subset size `r`, even though the
input file itself looks small.

## Dataset Used

The most stable test case for this explanation was:

- file: `summary_skate_a.csv`
- event filter: `e1,e2,e3,e4,e5,e6,e7,e8`
- coverage threshold: `t = 100`

After filtering, this run had:

- `26` valid rows
- `5` unique filtered sequences
- `159` distinct DAGs in the global set `S`

That last number, `|S| = 159`, is the important one. The expensive part of the
algorithm does **not** search over rows directly. It searches over combinations
of DAG patterns generated from the rows.

## What Happens As `r` Grows

Measured on this dataset:

- `r = 3`
  - qualifying subsets `|C| = 11,044`
  - subset-search time about `0.03s`
- `r = 4`
  - qualifying subsets `|C| = 1,607,883`
  - subset-search time about `2.38s`
- `r = 5`
  - already impractical in the older fully materialized search path
  - interrupted during enumeration because the number of valid subsets grows too quickly

The main issue is that increasing `r` does **not** increase runtime linearly.
It increases the number of valid DAG combinations explosively.

In plain language:

- at `r = 3`, the engine already finds over eleven thousand valid combinations
- at `r = 4`, it jumps to over **1.6 million**
- at `r = 5`, the exact search becomes expensive enough that it is not practical for presentation/demo use

## Why This Happens

The computational bottleneck is **combinatorial explosion**.

The pipeline is:

1. generate all sequence-compatible DAGs for the filtered data
2. deduplicate them into a global set `S`
3. search all valid subsets of `S` up to size `r`
4. run source detection on the qualifying subsets

Even with only `26` rows, once `|S| = 159`, the number of possible valid DAG
subsets can become extremely large.

So the limitation is **not** mainly:

- raw row count
- file size
- matrix/vector math

It is mainly:

- the number of distinct DAGs generated from the data
- how many of those DAGs can form valid exact subsets under the rules

## Why `t = 100` and Bidirectional Detection Also Matter

For this same dataset, with `r = 3`:

- source detection with bidirectional checking disabled took about `0.16s`
- source detection with bidirectional checking enabled took about `19.48s`

So even when subset generation is fast, the exact source step can become very
expensive when bidirectional arrows must also be checked.

## Key Conclusion

We could not comfortably go beyond `r = 4` on the figure skating data because
the exact algorithm starts producing an enormous number of valid DAG
combinations. By `r = 4`, the search is already in the millions of subsets, and
by `r = 5` the computation becomes impractical for normal interactive use.

This is an expected consequence of exact combinatorial search, not a simple bug
in the implementation.

## Practical Interpretation For Presentation

The shortest accurate summary is:

> We were able to analyze the figure skating data exactly up to `r = 4`, but
> going beyond that became computationally expensive because the number of valid
> DAG combinations grows explosively. The bottleneck is the exact combinatorial
> search itself, especially once source detection and bidirectional checks are included.
