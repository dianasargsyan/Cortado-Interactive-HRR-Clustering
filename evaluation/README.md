# Evaluation of Rotation-HRR

The evaluation compares the distance of Rotation-HRR with five existing methods (the activity profile, 3-grams, pq-grams, binary branches and the tree edit distance by APTED) on six public event logs and on a synthetic dataset. Since no clustering of variants is the correct one, the methods are not scored against a ground truth. Instead, variants are modified in known ways, and each experiment checks the response that the modification requires: whether a distance detects the modification, whether it grows as the modification grows or becomes more numerous, and whether it stays the same when the activities are renamed. Further experiments compare the methods on every pair of variants of a log, time them, fix the settings of Rotation-HRR and check the analyst's inputs.

## Layout

| Path | Contents |
|---|---|
| `evaluation/` | The package: the corpora (`corpus.py`, `synthetic.py`, `dataset.py`, `universe.py`), the methods compared (`methods.py`, `baselines.py`, `batch_hrr.py`), the modifications (`probes.py`, `probe_sets.py`, `phase2_probes.py`, `orders.py`), the analyst's inputs (`edited.py`), the settings (`config.py`) and the results table (`results.py`) |
| `evaluation/experiments/` | One script per experiment, and `run_all.sh`, which runs them all in order |
| `evaluation/tests/` | The tests |
| `evaluation/java_apted/` | APTED, the authors' Java implementation of the tree edit distance, and a driver for many pairs |
| `rotation_hrr/` | The encoding, shared with the tool |
| `cache/variants/` | The variants of the six logs, extracted with Cortado |

## Setup

The results were computed with Python 3.10 and the package versions in `requirements-evaluation.txt`, which also pins cortado-core. Since the tool pins a different cortado-core, a separate environment is recommended. From the repository root:

```
python3.10 -m venv .venv-evaluation
source .venv-evaluation/bin/activate
pip install -r requirements-evaluation.txt
pip install -e .
```

The tree edit distance needs a Java JDK 11 or later (tested with OpenJDK 21); APTED is compiled on first use. Every experiment checks the package versions first and stops if they differ, since other versions can give other numbers.

## Data

The variants of the six logs are included in `cache/variants/`, so the experiments run without the event logs. To extract them again, download the logs from 4TU.ResearchData into `data/` under the file names below and run `python evaluation/experiments/03_cache_variants.py domestic permit sepsis bpic15_1 bpi2012 bpi2017`.

| Log | File in `data/` | Source |
|---|---|---|
| Domestic Declarations | `DomesticDeclarations.xes` | van Dongen (2020), [10.4121/uuid:3f422315-ed9d-4882-891f-e180b5b4feb5](https://doi.org/10.4121/uuid:3f422315-ed9d-4882-891f-e180b5b4feb5) |
| Permit Log | `PermitLog.xes` | van Dongen (2020), [10.4121/uuid:ea03d361-a7cd-4f5e-83d8-5fbdf0362550](https://doi.org/10.4121/uuid:ea03d361-a7cd-4f5e-83d8-5fbdf0362550) |
| Sepsis Cases | `Sepsis Cases - Event Log.xes` | Mannhardt (2016), [10.4121/uuid:915d2bfb-7e84-49ad-a286-dc35f063a460](https://doi.org/10.4121/uuid:915d2bfb-7e84-49ad-a286-dc35f063a460) |
| BPIC15_1 | `BPIC15_1.xes` | van Dongen (2015), [10.4121/uuid:a0addfda-2044-4541-a450-fdcc9fe16d17](https://doi.org/10.4121/uuid:a0addfda-2044-4541-a450-fdcc9fe16d17) |
| BPI Challenge 2012 | `BPI_Challenge_2012.xes` | van Dongen (2012), [10.4121/uuid:3926db30-f712-4394-aebc-75976070e91f](https://doi.org/10.4121/uuid:3926db30-f712-4394-aebc-75976070e91f) |
| BPI Challenge 2017 | `BPI Challenge 2017.xes` | van Dongen (2017), [10.4121/uuid:5f3067df-f10b-45da-b98b-86ae4c7a310b](https://doi.org/10.4121/uuid:5f3067df-f10b-45da-b98b-86ae4c7a310b) |

## Running

```
bash evaluation/experiments/run_all.sh                    # every experiment, in order
QUICK=1 bash evaluation/experiments/run_all.sh            # every experiment on a small input
python evaluation/experiments/41_corpus_methods.py        # one experiment
python -m pytest                                          # the tests
```

`results/thesis_results.csv.gz` holds the results table from which the tables and figures of the thesis were drawn (read it with `evaluation.results.read`). Every experiment appends its rows to `results/results.csv`; `run_all.sh` writes a log with the time of each step next to it. Each row records the git commit of the code that computed it, and `evaluation/results.py` (`check_final`) refuses a table whose rows come from more than one commit or from uncommitted code. The full run takes many hours: the tree edit distance on BPI Challenge 2012 and 2017 takes the longest.

## Experiments

The docstring at the top of each script describes its settings and output.

| Script | Question |
|---|---|
| `03_cache_variants.py` | Extracts the variants of each log with Cortado and caches them |
| `16_log_profile.py` | The properties of each candidate log that decide whether it belongs in the evaluation |
| `17_chaining_check.py` | Which clustering algorithm: does one cluster swallow most of the log? |
| `21_positions.py` | Does every activity sit at its average place over every order the variant allows? |
| `22_universe.py` | Every variant up to four activities, and every pair described by which properties differ |
| `25_paired_layout.py` | Does pairing the frequency banks remove the effect of a pair's direction? |
| `26_dimension_noise.py` | How much a new seed changes the distances, at every dimension and setting of the weights |
| `27_kernels.py` | How far can position and depth rotate before a larger move stops looking larger? |
| `28_floors.py` | Do scale and sign of the weights matter? Exact identities on every synthetic corpus |
| `29_admissibility.py` | Which weights are allowed, and in which steps a weight still changes the ranking |
| `30_paths.py` | The modifications of the synthetic dataset, counted |
| `31_real_bases.py` | Real variants as base variants, and what the set of modifications costs |
| `34_response.py` | How much the ranking changes as a weight moves, against how much a new seed changes it |
| `35_direction_final.py` | Does Rotation-HRR score a pair differently for pointing one way in time or the other? |
| `41_corpus_methods.py` | Variants at distance 0, agreement with Rotation-HRR and the computing time, per log |
| `42_capability_methods.py` | Detection, growth with the size and the number of modifications, and renaming, for every method |
| `43_scaling.py` | How each method's time for every pair grows with the number of variants |
| `45_edit_checks.py` | Does each of the analyst's inputs change what it states and only that? |
| `46_edit_latency.py` | How long the analyst waits for a new clustering after an input |
