# FraudShield

Transaction Fraud Detection & Risk Engine

FraudShield is a portfolio project covering transaction data inspection,
fraud modeling, risk decision policies, and an API with persistent
decision records.

The current version recommends ALLOW or REVIEW using a frozen
machine learning model and a fixed decision threshold.

## Project Status

Implemented:
- Transaction data inspection and validation.
- Chronological training, validation, and test splits.
- Basic transaction features and historical feature experiments.
- Logistic regression and decision tree comparisons.
- Threshold analysis and daily review workload evaluation.
- Frozen model artifacts with integrity checks.
- Internal test evaluation and risk engine replay verification.
- FastAPI transaction scoring service.
- Request logging and SQLite decision storage.
- Optional idempotency keys for repeated requests.
- Command-line decision inspection and monitoring.
- Automated tests for the risk engine, API, and storage components.

A rebuild in a separate local project copy reproduced the reported
internal test metrics and passed risk engine replay checks.
All 32 automated tests passed in that rebuild environment.

All 30 April 2018 raw files were verified against a pinned upstream
commit using SHA-256 hashes.

Reproduction and local API demo instructions are available.
A complete fresh-machine walkthrough has not yet been verified.

## Business Problem

A payment provider needs to identify suspicious transactions while
limiting unnecessary reviews of legitimate transactions.

FraudShield explores the trade-off between:
- Detecting fraudulent transactions.
- Flagging legitimate transactions for review.
- Keeping daily review workloads manageable.

The system simulates risk recommendations. It does not process payments
or operate a real fraud investigation workflow.

## Current Decision Policy

Model version: `fraudshield-v1`  
Policy version: `review-policy-v1`  
Decision threshold: `0.05`

| Risk score | Recommendation |
| --- | --- |
| Below 0.05 | ALLOW |
| At or above 0.05 | REVIEW |

REVIEW means the transaction is flagged for further investigation.
It does not establish that fraud occurred.

The current version does not implement BLOCK decisions.

## Dataset and Evaluation Design

The project uses synthetic transaction data from the
[Fraud Detection Handbook](https://fraud-detection-handbook.github.io/fraud-detection-handbook/Chapter_3_GettingStarted/SimulatedDataset.html).

The working dataset covers April 1–30, 2018.

| Split | Transaction dates | Purpose |
| --- | --- | --- |
| Training | April 1–18 | Fit models and preprocessing |
| Validation | April 19–24 | Compare candidates and select the policy |
| Internal test | April 25–30 | Evaluate the frozen model and policy |

Transactions are split chronologically to evaluate performance on
a later period.

The April dataset was previously explored during project development.
The test results are therefore presented as an internal evaluation,
not a pristine independent benchmark.

Dataset license and redistribution review remain pending.
Raw datasets and trained model files are excluded from Git.

## Features and Model Selection

The selected candidate is `logistic_basic`, a logistic regression
pipeline using:

- `TX_AMOUNT`: transaction amount.
- `TX_HOUR`: hour derived from the transaction timestamp.
- `TX_IS_WEEKEND`: weekend indicator derived from the timestamp.

`TRANSACTION_ID` identifies a request's transaction and is not a
predictive feature.

`TX_FRAUD` is the target label.
`TX_FRAUD_SCENARIO` contains simulator scenario information.
Neither is included in model inputs.

Experiments also include customer and terminal history features
computed over the preceding 24 hours. These features exclude
transactions at or after the current transaction timestamp.

Historical features were evaluated but are not used by the selected
API model.

The selected model and threshold were chosen using validation results,
prioritizing fraud recall under an assumed review capacity of
100 transactions per day.

This capacity is an evaluation assumption, not a limit enforced by
the API.

## Internal Test Results

Evaluation period: April 25–30, 2018.  
Threshold: `0.05`.

| Metric | Result |
| --- | ---: |
| Transactions | 57,767 |
| Fraudulent transactions | 526 |
| Average Precision | 0.2729 |
| Precision at the selected threshold | 38.98% |
| Recall at the selected threshold | 26.24% |
| Fraudulent transactions flagged (TP) | 138 |
| Legitimate transactions flagged (FP) | 216 |
| Fraudulent transactions missed (FN) | 388 |
| Legitimate transactions allowed (TN) | 57,025 |
| Total REVIEW recommendations | 354 |
| Maximum REVIEW recommendations in one day | 70 |
| Days exceeding the assumed capacity of 100 | 0 |

The policy flagged 138 of 526 fraudulent transactions while sending
216 legitimate transactions for review.

The remaining 388 fraudulent transactions were missed. This is a
material limitation of the current model.

Evidence:
[Internal test evaluation](reports/frozen_v1/test_evaluation.json)

## Risk Engine Consistency

A replay compared risk engine outputs with saved batch predictions
for all 57,767 internal test transactions.

Results:
- Score mismatches beyond the configured numerical tolerance: 0.
- Decision mismatches: 0.
- Replay status: PASS.

This verifies agreement between batch predictions and the risk engine.
It does not establish production throughput or real-world fraud performance.

Evidence:
[Risk engine replay](reports/frozen_v1/risk_engine_replay.json)

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/health` | Service readiness and version information |
| POST | `/predict` | Score a transaction and return a recommendation |
| GET | `/docs` | Interactive API documentation |

Example request body for `/predict`:

```json
{
  "TRANSACTION_ID": 2001,
  "TX_DATETIME": "2018-05-01T10:00:00",
  "TX_AMOUNT": 75.0
}
```

The current input contract uses timestamps without a timezone offset.

Responses include the transaction ID, risk score, threshold,
decision, reason, model version, and policy version.

### Idempotency

Clients can supply an `Idempotency-Key` header.

- The same key and normalized input return the stored result.
- Reusing the key with different input returns HTTP 409.
- Requests without a key are processed as new requests.

The response header `X-Idempotent-Replay` indicates whether the result
was reused.

## Run Locally: Existing Project Setup

These commands assume:
- Windows PowerShell.
- Python 3.12.2 and the project's `.venv` are already configured.
- Project dependencies are installed.
- Compatible frozen artifacts are available:
  - `models/frozen_v1/model.pkl`
  - `models/frozen_v1/selection.json`

Run commands from the project root.

A fresh clone does not include the ignored model and data artifacts.
Dependency installation alone is not sufficient to run the API.

Follow the [reproduction guide](docs/reproduction.md) to download
the verified dataset and build the frozen model artifacts.
See the [local API demo](docs/demo.md) for scoring and replay examples.

Start the API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn api:app --app-dir src --host 127.0.0.1 --port 8000
```

Keep this terminal running.

Open:
- Interactive documentation: http://127.0.0.1:8000/docs
- Health endpoint: http://127.0.0.1:8000/health

The root URL `/` does not have an application route.

Stop the server with `Ctrl+C`.

## Tests and Operational Inspection

Run the automated test suite:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

A successful run ends with `OK` and a nonzero number of executed tests.

Inspect recent stored decisions:

```powershell
.\.venv\Scripts\python.exe src/inspect_decisions.py
```

Summarize stored decisions:

```powershell
.\.venv\Scripts\python.exe src/monitor_decisions.py
```

Runtime decision records are stored locally at:

`data/runtime/fraudshield.db`

Monitoring summarizes stored decisions by their UTC recording date.
It does not measure fraud detection performance because runtime
records do not contain confirmed fraud outcomes.

## Dependencies

- `requirements.txt`: direct project dependency declarations.
- `requirements-frozen.txt`: exact installed package versions captured
  from the development environment.

The frozen requirements file is an environment snapshot.
It does not guarantee identical behavior across operating systems.

## Project Structure

| Location | Contents |
| --- | --- |
| `src/` | Data preparation, modeling, risk engine, API, and monitoring |
| `tests/` | Automated checks |
| `docs/` | Evaluation design, model documentation, and operating guide |
| `reports/` | Saved experiment and evaluation reports |
| `data/` | Local datasets and runtime database; excluded from Git |
| `models/` | Local trained artifacts and metadata; excluded from Git |
| `notebooks/` | Exploration workspace |

## Documentation

- [Evaluation plan](docs/evaluation_plan.md)
- [Model card](docs/model_card.md)
- [Operating guide](docs/runbook.md)
- [Validation model comparison](reports/history_v1/model_comparison_validation.json)
- [System architecture](docs/architecture.md)
- [Local API demo](docs/demo.md)
- [Reproduction guide](docs/reproduction.md)
- [Dataset source verification](reports/dataset_source_verification.json)

## Limitations and Remaining Work

- Results describe synthetic data from a limited time period.
- Risk scores have not been established as calibrated fraud probabilities.
- The current policy misses a substantial proportion of fraud.
- Review workloads may exceed the assumed capacity on future data.
- Monitoring covers operational decisions, not confirmed fraud outcomes.
- Authentication, production load testing, and deployment hardening
  are outside the current implementation.
- A review dashboard and automatic blocking are not implemented.
- The complete documented workflow has not yet been verified on a fresh machine.
- Dataset license and redistribution review remain pending.