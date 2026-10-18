# FraudShield Local API Demo

This demo shows transaction scoring and idempotent request replay.

## Prerequisites

- Run commands from the project root in Windows PowerShell.
- Install dependencies in `.venv`.
- Prepare `models/frozen_v1/model.pkl` and `selection.json`
  by following [the reproduction guide](reproduction.md).
- Use two terminals: one for the server and one for requests.

Cloning the repository alone does not provide the model artifacts.

## 1. Start the server

In the server terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn api:app --app-dir src --host 127.0.0.1 --port 8002
```

Keep this terminal running.

Expected startup message:

```text
Uvicorn running on http://127.0.0.1:8002
```

If port 8002 is occupied, choose another available port
and update the request address below to match.

## 2. Send a transaction

Open a second PowerShell terminal. Run this block:

```powershell
$ErrorActionPreference = "Stop"

$alamat = "http://127.0.0.1:8002"

$headerDemo = @{
    "Idempotency-Key" = "portfolio-" + [guid]::NewGuid().ToString()
}

$transaksiDemo = @{
    TRANSACTION_ID = 2001
    TX_DATETIME = "2018-05-01T10:00:00"
    TX_AMOUNT = 75.0
} | ConvertTo-Json

$responsPertama = Invoke-WebRequest -Uri "$alamat/predict" -Method Post -ContentType "application/json" -Headers $headerDemo -Body $transaksiDemo -UseBasicParsing

$responsPertama.Content | ConvertFrom-Json | Format-List

Write-Host "Replay:" $responsPertama.Headers["X-Idempotent-Replay"]
```

Observed result for the verified frozen model:

```text
transaction_id : 2001
risk_score     : 0.0037923385079987712
threshold      : 0.05
decision       : ALLOW
reason         : SCORE_BELOW_THRESHOLD
model_version  : fraudshield-v1
policy_version : review-policy-v1

Replay: false
```

Small floating-point differences may occur across environments.

The score is below the threshold, so the policy returns ALLOW.
This is a model-based recommendation, not proof that the
transaction is legitimate.

The first request creates a decision record in the local database.

## 3. Repeat the same request

Run this block in the same request terminal.
Do not regenerate the idempotency key between the two requests.

```powershell
$responsUlang = Invoke-WebRequest -Uri "$alamat/predict" -Method Post -ContentType "application/json" -Headers $headerDemo -Body $transaksiDemo -UseBasicParsing

$responsUlang.Content | ConvertFrom-Json | Format-List

Write-Host "Replay:" $responsUlang.Headers["X-Idempotent-Replay"]

Write-Host "ID catatan awal:" $responsPertama.Headers["X-Original-Request-ID"]

Write-Host "ID catatan ulang:" $responsUlang.Headers["X-Original-Request-ID"]
```

Expected behavior:

- The score and decision match the first response.
- `X-Idempotent-Replay` is `true`.
- Both `X-Original-Request-ID` values are present and identical.

The repeated request returns the stored decision.
Request IDs will differ between independent demo runs.

A new idempotency key starts a new scoring operation, even if
the transaction ID has been used before.

## 4. View the API documentation

While the server is running, open:

http://127.0.0.1:8002/docs

This local address only works on the computer running the API.

## 5. Stop the server

Select the server terminal and press Ctrl+C.

Stored decision records remain in:
`data/runtime/fraudshield.db`.

## Scope of this demo

This walkthrough demonstrates one ALLOW response and successful
replay of an identical request.

It does not measure fraud detection performance, concurrent
throughput, or production readiness.
