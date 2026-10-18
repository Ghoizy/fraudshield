# Reproducing the Model Pipeline

## Scope and Verification Status

This guide describes the script sequence from existing April 2018
raw transaction files to the frozen model used by FraudShield.

The sequence has been checked against the source code.
A complete rebuild in a separate project copy remains to be verified.

This guide assumes the raw data is already available.
Dataset acquisition and redistribution instructions are still pending.

## Prerequisites

- Windows PowerShell.
- Python 3.12.2.
- Project source code.
- Dependencies from `requirements-frozen.txt`.
- Thirty trusted daily dataset files in `data/raw/`, named:
  - `2018-04-01.pkl`
  - ...
  - `2018-04-30.pkl`

Only load pickle files from a trusted source.

Run all commands from the project root.

## Preserve the Existing Experiment

Perform a rebuild in a separate project copy with its own environment,
data outputs, and model outputs.

Several scripts overwrite their output files.

Do not delete the existing frozen model to force a rebuild.
`freeze_selected_model.py` intentionally stops when
`models/frozen_v1` already exists.

The original saved reports are reference results. A new run must not
be presented as matching those results until its outputs are compared.

## Environment Setup

In the separate project copy, create an environment using Python 3.12:

```powershell
py -3.12 -m venv .venv
```

Check the actual Python version:

```powershell
.\.venv\Scripts\python.exe --version
```

The reference development version is Python 3.12.2.

Install the captured dependency versions:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-frozen.txt
```

Check dependency compatibility:

```powershell
.\.venv\Scripts\python.exe -m pip check
```

Expected result:

```text
No broken requirements found.
```

This check verifies declared dependency compatibility. It does not
replace functional tests or verify model results.

## Step 1: Build Historical Features

```powershell
.\.venv\Scripts\python.exe src/build_history.py
```

Purpose:
- Read the 30 daily raw files.
- Sort transactions by timestamp and transaction ID.
- Calculate customer and terminal history features.
- Compare a sample of up to 30 transactions with reference calculations.
- Save the combined dataset.

History covers `[transaction time - 24 hours, transaction time)`.
Transactions at the current timestamp are excluded.

History features use transaction information, not fraud labels.
History before April 1 is unavailable.

Output:

```text
data/processed/transactions_history_24h.pkl
```

For the existing dataset, the sample check is expected to report:

```text
PEMERIKSAAN LULUS: 30 transaksi cocok.
```

`history_features.py` supplies functions used by this script.
It is not a separate command-line pipeline step.

## Step 2: Prepare Training, Validation, and Test Data

```powershell
.\.venv\Scripts\python.exe src/prepare_history_dataset.py
```

Purpose:
- Add transaction hour and weekend features.
- Validate required columns, labels, IDs, and numerical values.
- Split the data chronologically.
- Save features, labels, and metadata together.

| Split | Inclusive start | Exclusive end |
| --- | --- | --- |
| Train | 2018-04-01 | 2018-04-19 |
| Validation | 2018-04-19 | 2018-04-25 |
| Test | 2018-04-25 | 2018-05-01 |

Outputs:

```text
data/processed/history_v1/train.pkl
data/processed/history_v1/validation.pkl
data/processed/history_v1/test.pkl
```

Each file contains:
- `X`: nine candidate input features.
- `y`: the fraud label.
- `metadata`: transaction identifiers and timestamps.

Expected completion message:

```text
PERSIAPAN DATA SELESAI
```

## Step 3: Train Logistic Regression Candidates

```powershell
.\.venv\Scripts\python.exe src/train_history_logistic.py
```

Purpose:
- Train a basic model with three features.
- Train a history model with nine features.
- Evaluate both on validation.
- Save models and validation scores.

Preprocessing is fitted within each pipeline using training data.
The script stops if Logistic Regression raises a convergence warning.

Outputs:

```text
models/history_v1/logistic_basic.pkl
models/history_v1/logistic_history.pkl
reports/history_v1/logistic_comparison_validation.json
data/processed/history_v1/logistic_validation_scores.pkl
```

Expected completion message:

```text
EKSPERIMEN LOGISTIC SELESAI
```

## Step 4: Compare Logistic Regression Thresholds

```powershell
.\.venv\Scripts\python.exe src/analyze_history_thresholds.py
```

Purpose:
- Read saved validation scores.
- Compare seven thresholds for each logistic model.
- Measure fraud detection and daily review workloads.

Thresholds:

```text
0.5, 0.2, 0.1, 0.05, 0.02, 0.01, 0.005
```

No model is retrained in this step.

Output:

```text
reports/history_v1/logistic_thresholds_validation.json
```

Expected completion message:

```text
ANALISIS THRESHOLD SELESAI
```

## Step 5: Train and Evaluate Decision Tree Candidates

```powershell
.\.venv\Scripts\python.exe src/train_history_tree.py
```

Purpose:
- Train basic and history Decision Tree models.
- Compare the same seven thresholds on validation.
- Measure daily review workloads.

Tree settings:
- `max_depth=5`
- `min_samples_leaf=50`
- `random_state=42`

Outputs:

```text
models/history_v1/tree_basic.pkl
models/history_v1/tree_history.pkl
reports/history_v1/tree_thresholds_validation.json
data/processed/history_v1/tree_validation_scores.pkl
```

Expected completion message:

```text
EKSPERIMEN TREE SELESAI
```

## Step 6: Compare All Candidates

```powershell
.\.venv\Scripts\python.exe src/compare_history_models.py
```

Purpose:
- Read logistic and tree threshold reports.
- Compare four model candidates across seven thresholds.
- Recommend a model and threshold using validation results.

Selection order:
1. Meet the assumed capacity of 100 reviews on every validation day.
2. Highest recall.
3. Lowest false positives.
4. Highest validation Average Precision.
5. Candidate name ascending for deterministic tie-breaking.
6. Highest threshold.

Output:

```text
reports/history_v1/model_comparison_validation.json
```

The recorded reference recommendation is:

```text
Candidate: logistic_basic
Threshold: 0.05
```

If the recommendation differs, investigate the input data, environment,
and preceding outputs before freezing a model.

Do not edit the report merely to match the reference recommendation.

## Step 7: Freeze the Selected Model

```powershell
.\.venv\Scripts\python.exe src/freeze_selected_model.py
```

Purpose:
- Check that the recommendation matches the reviewed choice.
- Recalculate validation metrics using the selected trained model.
- Compare them with the selection report.
- Save a model copy with the fixed threshold and version.
- Record file hashes and environment versions.

This step does not retrain the model.

The current script expects:
- Candidate: `logistic_basic`
- Threshold: `0.05`
- Review capacity assumption: 100 per day.

Outputs:

```text
models/frozen_v1/model.pkl
models/frozen_v1/selection.json
```

Expected completion messages include:

```text
PEMERIKSAAN VALIDATION COCOK
MODEL DAN THRESHOLD TERSIMPAN
CHECKPOINT 8A SELESAI
```

The script hashes the test dataset to record its identity.
It does not calculate test performance or use test labels for selection.

## Completion and Next Checks

The frozen artifacts are the model files required by the API.

A successful freeze does not, by itself, verify:
- Agreement with the reference internal test results.
- Batch-versus-risk-engine replay consistency.
- API and storage behavior.

Those checks follow the rebuild.

Rebuilt file hashes may differ because of serialization, environment,
or metadata such as creation timestamps. Compare model behavior and
metrics as well as recording file identity.

## Earlier Baseline Experiments

`split_dataset.py` and `train_baseline.py` belong to the earlier
baseline experiment.

They generate files outside the `history_v1` pipeline and are not
prerequisites for the seven steps above.

Their reports remain useful as part of the experiment history.