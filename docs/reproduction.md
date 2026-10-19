# Reproducing the Model Pipeline

## Scope and Verification Status

This guide describes the script sequence from existing April 2018
raw transaction files to the frozen model used by FraudShield.

The sequence has been checked against the source code.
A rebuild was completed in a separate local project copy on
October 18, 2026, using the existing April 2018 raw dataset.

The reported internal test metrics matched the reference evaluation.
Risk engine replay passed for all 57,767 test transactions, with zero
score mismatches beyond tolerance and zero decision mismatches.

This verifies a local rebuild using the available raw data.
It does not verify dataset acquisition on a fresh machine or
cross-platform reproducibility.

Rebuild evidence:
- [Test evaluation](../reports/rebuild_20261018/test_evaluation.json)
- [Risk engine replay](../reports/rebuild_20261018/risk_engine_replay.json)

If the raw files are not yet available, follow
[Download the verified dataset](#download-the-verified-dataset)
before running Step 1.

The download instructions use a pinned upstream commit and verify
each file against the recorded SHA-256 hash.

Dataset license and redistribution review remain pending.

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

## Step 8: Evaluate the Frozen Model

Run this step only after successfully completing Step 7
in the separate rebuild copy.

The repository includes reference evaluation reports.
Preserve them before generating new evaluation results:

```powershell
if (Test-Path ".\reports\frozen_v1") {
    if (Test-Path ".\reports\reference_frozen_v1") {
        throw "Reference backup already exists. Inspect both report folders before proceeding."
    }

    Move-Item -Path ".\reports\frozen_v1" -Destination ".\reports\reference_frozen_v1"
}
```

This moves reports within the rebuild copy.
It does not move or delete the frozen model.

If the command reports an error, stop and inspect the folders
before continuing.

Run the evaluation:

```powershell
.\.venv\Scripts\python.exe src/evaluate_frozen_model.py
```

Outputs:

- `reports/frozen_v1/test_evaluation.json`
- `data/processed/frozen_v1/test_predictions.pkl`

Compare the new metrics with the reference report.
Matching results must be observed, not assumed.

Reference results include:

| Metric | Reference |
|---|---:|
| Transactions | 57,767 |
| Fraudulent transactions | 526 |
| Average Precision | 0.2728602084917219 |
| True positives | 138 |
| False positives | 216 |
| False negatives | 388 |
| True negatives | 57,025 |
| Total REVIEW | 354 |
| Maximum daily REVIEW | 70 |

## Step 9: Verify Risk Engine Consistency

After the evaluation completes successfully:

```powershell
.\.venv\Scripts\python.exe src/replay_risk_engine.py
```

Output:

`reports/frozen_v1/risk_engine_replay.json`

Expected reference behavior:

- Status: PASS.
- Transactions checked: 57,767.
- Score mismatches beyond tolerance: 0.
- Decision mismatches: 0.

Replay checks agreement with saved batch predictions.
It is not an HTTP API load test.

## Step 10: Run Application Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

The verified rebuild ran 32 tests and finished with `OK`.
Execution time may vary.

After the tests pass, follow the
[local API demo](demo.md) to start the service and send requests.

## Interpreting Rebuild Results

Rebuilt artifact hashes may differ because of serialization,
environment differences, or metadata such as creation timestamps.

Record file identity and compare model behavior and evaluation
metrics. Do not claim identical results solely because the scripts
completed without errors.

## Application verification after local rebuild

Verification date: October 18, 2026.

The automated test suite completed in the separate
fraudshield-rebuild project:

- Tests run: 32.
- Result: OK.
- Reported duration: 1.907 seconds.

The rebuilt application started successfully on port 8001.
Its /health endpoint returned HTTP 200 with:

- status: ready
- model_version: fraudshield-v1
- policy_version: review-policy-v1

A StarletteDeprecationWarning concerning the TestClient
HTTP dependency was observed. It did not fail the test run.

These results verify the tested behavior in the local rebuild
environment. They do not establish production readiness or
cross-platform reproducibility.

## Upstream dataset source

FraudShield uses synthetic transaction data from the
Fraud Detection Handbook.

Simulator documentation:
https://fraud-detection-handbook.github.io/fraud-detection-handbook/Chapter_3_GettingStarted/SimulatedDataset.html

Dataset repository:
https://github.com/Fraud-Detection-Handbook/simulated-data-raw

This experiment uses 30 daily files, from 2018-04-01.pkl
through 2018-04-30.pkl, stored locally in data/raw/.

All 30 local raw files were verified against upstream commit
`6e67dbd0a3bfe0d7ec33abc4bce5f37cd4ff0d6a`.

Verification results:
- Files checked: 30.
- Matching SHA-256 hashes: 30.
- Different files: 0.

This confirms byte-for-byte agreement between the local raw
files and the upstream files at the recorded commit.

Evidence:
[Dataset source verification](../reports/dataset_source_verification.json)

## Download the verified dataset

Run these commands in PowerShell from the project root.
Git and Python are not required for this download step.

The verification report must be available at:
`reports/dataset_source_verification.json`.

```powershell
& {
    $ErrorActionPreference = "Stop"

    $report = Get-Content ".\reports\dataset_source_verification.json" -Raw |
        ConvertFrom-Json

    $commit = "6e67dbd0a3bfe0d7ec33abc4bce5f37cd4ff0d6a"

    if ($report.source_commit -ne $commit) {
        throw "The verification report references a different source commit."
    }

    New-Item -ItemType Directory -Path ".\data\raw" -Force |
        Out-Null

    $startDate = Get-Date -Year 2018 -Month 4 -Day 1

    for ($day = 0; $day -lt 30; $day++) {
        $name = $startDate.AddDays($day).ToString("yyyy-MM-dd") + ".pkl"
        $destination = Join-Path ".\data\raw" $name

        $entry = @($report.files | Where-Object { $_.file -eq $name })

        if ($entry.Count -ne 1) {
            throw "Missing or duplicate verification entry: $name"
        }

        if (-not (Test-Path -LiteralPath $destination)) {
            $url = "https://raw.githubusercontent.com/Fraud-Detection-Handbook/simulated-data-raw/$commit/data/$name"

            Invoke-WebRequest -Uri $url -OutFile $destination -TimeoutSec 60
        }

        $actualHash = (
            Get-FileHash -LiteralPath $destination -Algorithm SHA256
        ).Hash

        if ($actualHash -ne $entry[0].sha256_sumber) {
            throw "SHA-256 mismatch: $name. Stop and inspect the file."
        }

        Write-Host "VERIFIED: $name"
    }

    Write-Host "All 30 April 2018 files are available and verified."
}
```

Existing files are checked and are not overwritten.
Missing files are downloaded from the pinned upstream commit.

If a download fails or a hash does not match, stop before
running the data-processing pipeline. A partial download may
need to be removed before retrying that individual file.

Expected final output:

```text
All 30 April 2018 files are available and verified.
```

After verification, follow the environment setup and pipeline
steps in this document.