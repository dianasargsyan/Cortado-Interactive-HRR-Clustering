# Interactive Variant Clustering with Rotation-HRR

This repository contains the implementation of the master's thesis **An Interactive Framework for Clustering Partially Ordered Event Data** (LMU Munich, 2026). It is based on Cortado and on the [Interactive Trace Clustering](https://github.com/DiwenS/Cortado-Interactive-Trace-Clustering) project, which added must-link and cannot-link constraints to Cortado's variant clustering. On top of these, it adds a variant clustering that the analyst steers while looking at the clusters:

- **Rotation-HRR**, an encoding of every variant tree as one vector. The distance of two variants detects which activities they contain, their order, which activities run in parallel and how deeply blocks are nested, and every order of a parallel block counts alike.
- **HRR clustering (COP-KMeans)**, a new algorithm in Cortado's variant clustering that clusters these vectors and keeps the must-link and cannot-link constraints during the clustering.
- **The analyst's inputs**: how much order and nesting count, declaring activities the same, ignoring an activity, and must-link and cannot-link constraints. Every input reclusters at once, starting from the clusters on the screen, and every earlier state can be brought back.
- **Cluster descriptions**: a representative variant for each cluster, the activities that set the cluster apart, and the variants that changed cluster after each input.
- **The evaluation**, which compares Rotation-HRR with the activity profile, k-grams, pq-grams, binary branches and the tree edit distance on six public event logs and a synthetic dataset.

https://github.com/user-attachments/assets/d44c56a2-25dc-4811-880b-6d17858c84f0


## Download and Run

### Requirements

- [Git](https://git-scm.com/downloads)
- [Python 3.10](https://www.python.org/downloads/) (64-bit)
- [Node.js](https://nodejs.org/en/download/) 18 or 20 (tested with 20.9)
- Optional: [Graphviz](https://graphviz.org/download/), used by PM4Py for some of Cortado's views

### Download

```
git clone https://github.com/dianasargsyan/Cortado-Interactive-HRR-Clustering.git
cd Cortado-Interactive-HRR-Clustering
```

Or download the repository as a ZIP file (Code → Download ZIP) and unpack it.

### Install and Start the Backend

From the repository root, create a Python environment, install Cortado's backend and this repository into it, and start the backend:

```
python3.10 -m venv .venv
source .venv/bin/activate            # on Windows: .venv\Scripts\activate
pip install -r src/backend/requirements.txt
pip install -e .
cd src/backend
python main.py
```

The backend runs on port 40000. Leave this terminal open.

### Install and Start the Frontend

In a second terminal, from the repository root:

```
cd src/frontend
npm install
npm start
```

Once the frontend is built, open http://localhost:4444/ in a browser. The first `npm install` and `npm start` take a few minutes.

### First Clustering

1. Import an event log (`.xes`) under **Files**.
2. Open **Functions → Variant Clustering**, select **HRR clustering (COP-KMeans)** and click **Apply**.

The standalone builds on Cortado's releases page do not contain this extension; run it from the code as above.


## Using the Clustering

[HRR_CLUSTERING.md](HRR_CLUSTERING.md) describes every input step by step, with screenshots: reading the clusters, changing how much order and nesting count, declaring activities the same, ignoring an activity, adding must-link and cannot-link constraints, and going back to an earlier clustering. The constrained clustering of the original project is described in [INTERACTIVE_CONSTRAINED_CLUSTERING.md](INTERACTIVE_CONSTRAINED_CLUSTERING.md).


## Evaluation

The evaluation compares the distance of Rotation-HRR with five existing methods on six public event logs and a synthetic dataset: whether each method detects a known modification of a variant, whether its distance grows as the modification grows or becomes more numerous, whether it stays the same when activities are renamed, how far the methods agree on every pair of variants, and how long each takes. It also checks the analyst's inputs and how long the analyst waits for a new clustering.

The evaluation runs separately from the tool, in its own Python environment, and its results table is included. How to set it up and run each experiment is described in [evaluation/README.md](evaluation/README.md).


## Repository Structure

| Path | Contents |
|---|---|
| `rotation_hrr/` | The encoding (`encoder.py`), the positions and depths of a variant tree (`tree_utils.py`), and the rewriting of variant trees for the analyst's inputs (`tree_rewrites.py`, `domain_knowledge.py`, `variant_enumeration.py`) |
| `src/backend/` | Cortado's backend, with the clustering endpoint (`api/routes/variants/hrr_clustering.py`) and COP-KMeans (`api/routes/variants/cop_kmeans.py`) |
| `src/frontend/` | Cortado's frontend, with the controls above the clusters (`src/app/components/variant-explorer/hrr-clustering-bar/`, `src/app/services/hrrClusteringService/`) and the changes to the Variant Explorer and the Activity Overview |
| `evaluation/` | The evaluation: the package, one script per experiment (`experiments/`), the tests (`tests/`) and APTED (`java_apted/`) |
| `cache/variants/`, `results/`, `data/` | The variants of the six event logs, the results table of the thesis, and the folder for the event logs |
| `images/`, `doc/` | The screenshots of the guides, and Cortado's user manual |
| `build_scripts/` | Cortado's scripts for building standalone applications |


## Credits and License

- [Cortado](https://github.com/cortado-tool/cortado) by the Cortado team (GPL-3.0), on which this repository is based
- [Interactive Trace Clustering](https://github.com/DiwenS/Cortado-Interactive-Trace-Clustering) by Diwen Shi et al., the must-link and cannot-link constraints and their controls
- [COP-Kmeans](https://github.com/Behrouz-Babaki/COP-Kmeans) by Behrouz Babaki (MIT), adapted in `cop_kmeans.py`
- [APTED](https://github.com/DatabaseGroup/apted) by Mateusz Pawlik and Nikolaus Augsten (MIT), in `evaluation/java_apted/`

This repository is licensed under the GPL-3.0, as Cortado.
