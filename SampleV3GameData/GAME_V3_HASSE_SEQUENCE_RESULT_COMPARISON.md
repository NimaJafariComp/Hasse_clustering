# Game v3 Hasse Result Comparison

This report compares the original Game v3 Hasse clustering result with the new
Hasse Sequence Clustering result on the same winning-episode sample data.

## Data

Sample files:

- `sequence_of_sets_formatted_Won.csv`
- `M_c_matrices_diagonal_1 ('e1', 'e2', 'e5', 'e6', 'e11') game_won.json`

The CSV contains the raw winning episode event sequences. The JSON file is the
old AlgV4 output: one strict ordering matrix `M_c` per episode over the selected
event set:

```text
e1,e2,e5,e6,e11
```

## Event Dictionary

| Code | Meaning |
|---|---|
| `e1` | Key collected. |
| `e2` | Explosive collected. |
| `e3` | Key not collected in this episode. |
| `e4` | Explosive not collected in this episode. |
| `e5` | Used explosive on rock. |
| `e6` | Used key on door. |
| `e7` | Failed interaction with explosive. |
| `e8` | Failed interaction with key. |
| `e9` | Episode won by blue door. |
| `e10` | Episode lost. |
| `e11` | Player collects treasure. |
| `e12` | Episode won by treasure. |

## Original Paper Hasse Clustering Result

The original Hasse clustering analysis used only:

```text
e1,e2,e5,e6,e11
```

Reported result:

```text
Found 186 high-coverage combinations (size = 2) covering all winning episodes.
G_cp contains 186 nodes and 8513 edges.
Identified 1 best combination:
nodes (343, 725)
```

The two best nodes were:

```text
Node 343:
e2 -> e5
e2 -> e11
e5 -> e11
```

As a Hasse/transitive-reduction pattern:

```text
e2 -> e5 -> e11
```

Meaning:

```text
Explosive collected -> explosive used on rock -> treasure collected
```

```text
Node 725:
e1 -> e6
e2 -> e5
e2 -> e6
e5 -> e6
```

As a Hasse/transitive-reduction pattern:

```text
e1 -> e6
e2 -> e5 -> e6
```

Meaning:

```text
Key collected -> key used on door
Explosive collected -> explosive used on rock -> key used on door
```

Together, nodes `(343, 725)` covered all winning episodes under the old
five-event analysis.

## New Hasse Sequence Clustering Result With Same Five Events

Using the new pipeline with:

```text
r = 2
t = 100
events filter = e1,e2,e5,e6,e11
```

the result is:

```text
valid sequences n = 119
|S| (distinct DAGs)      = 126
|C| (qualifying subsets) = 137
sources                  = 1

Source subset:
{ e1->e6 e2->e5 e5->e6  |  e2->e5 e5->e11 }
```

This is the same semantic best result as old nodes `(343, 725)`:

```text
Old Node 725:
e1->e6, e2->e5, e5->e6

New DAG 1:
e1->e6, e2->e5, e5->e6
```

```text
Old Node 343:
e2->e5, e5->e11

New DAG 2:
e2->e5, e5->e11
```

The final best pattern agrees. The counts differ because the pipelines count
different objects:

- old pipeline counts combinations of fixed Hasse graph node IDs;
- new pipeline counts generated DAG subsets;
- old pipeline uses AlgV4 `M_c` matrices;
- new pipeline generates sequence-compatible DAGs directly;
- current new pipeline drops repeated-event sequences before filtering, giving
  `n = 119` valid sequences instead of all `125` CSV rows.

## New Full-Event Result

The original Hasse clustering pipeline could not realistically analyze all
twelve events:

```text
e1,e2,e3,e4,e5,e6,e7,e8,e9,e10,e11,e12
```

because it would require a global `n = 12` poset/Hasse universe and a graph over
that universe. That is computationally infeasible with the old fixed-poset
approach.

The new Hasse Sequence Clustering pipeline does not generate all possible
twelve-event posets. It generates only DAGs compatible with the observed
sequences, so this full-event run is feasible.

Using:

```text
r = 2
t = 100
events filter = e1,e2,e3,e4,e5,e6,e7,e8,e9,e10,e11,e12
```

the browser result was:

```text
valid sequences n = 119
|S| (distinct DAGs)      = 19864
|C| (qualifying subsets) = 18113
sources                  = 1
```

The single source subset contains two DAGs:

```text
DAG 1:
e1 -> e6
e2 -> e5
e5 -> e6
e6 -> e9
```

Meaning:

```text
Key collected -> key used on door
Explosive collected -> explosive used on rock -> key used on door -> blue-door win
```

Plain interpretation:

```text
Blue-door route:
collect key and explosive, use explosive on rock, use key on door, then win by blue door.
```

```text
DAG 2:
e2 -> e5
e5 -> e11
e11 -> e12
```

Meaning:

```text
Explosive collected -> explosive used on rock -> treasure collected -> treasure win
```

Plain interpretation:

```text
Treasure route:
collect explosive, use explosive on rock, collect treasure, then win by treasure.
```

## Main Comparison

The full-event result preserves the original paper patterns and extends them
with terminal outcome events.

Original paper pattern:

```text
e1 -> e6
e2 -> e5 -> e6
```

New full-event pattern:

```text
e1 -> e6
e2 -> e5 -> e6 -> e9
```

Added event:

```text
e9 = blue-door win
```

Original paper pattern:

```text
e2 -> e5 -> e11
```

New full-event pattern:

```text
e2 -> e5 -> e11 -> e12
```

Added event:

```text
e12 = treasure win
```

So the new result is not contradictory to the old Hasse clustering result. It is
the same core result, enriched by allowing the outcome events `e9` and `e12` to
participate in the analysis.

## Conclusion

The original Hasse clustering result found two complementary winning patterns:

```text
1. explosive/rock/treasure pattern
2. key/explosive/door pattern
```

The new Hasse Sequence Clustering result recovers the same two core patterns and
adds the actual terminal outcome events:

```text
1. key/explosive/door -> blue-door win
2. explosive/rock/treasure -> treasure win
```

This is a stronger and more interpretable result because it uses all twelve
event codes instead of only the five-event subset used by the original paper
pipeline.

