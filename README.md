# FraudShield

Transaction Fraud Detection & Risk Engine

## Project Status
Design and environment setup.
No model has been trained or evaluated yet.

## Business Problem
A payment provider needs to identify fraudulent transactions
while limiting disruption to legitimate customers and keeping
manual review workloads manageable.

## Objective
Build a reproducible system that scores transaction risk and
recommends ALLOW, REVIEW, or BLOCK.

## Intended Users
- Payment applications requesting transaction risk assessments.
- Fraud analysts reviewing suspicious transactions.
- Risk managers evaluating decision policies.

## Initial Scope
- Transaction data validation and exploration.
- Historical feature engineering.
- Rule-based and machine learning baselines.
- Evaluation using chronological data splits.
- Configurable risk decision policies.
- Transaction scoring API.
- Review dashboard and decision audit logs.

## Data
Initial candidate: synthetic transaction data from the
Fraud Detection Handbook.

Source:
https://fraud-detection-handbook.github.io/fraud-detection-handbook/Chapter_3_GettingStarted/SimulatedDataset.html

Dataset selection is pending license and data suitability review.
Results will describe performance on synthetic data.

## Evaluation Plan
- Average Precision.
- Precision within a defined review capacity.
- Fraud recall for flagged transactions.
- False-positive block rate.
- Manual review rate.
- Simulated policy costs under documented assumptions.
- API latency and error rate under a defined test workload.

## Boundaries
Decisions are simulated; the system does not process real payments.
Model performance and business benefits have not yet been measured.

## Project Structure
- data/: datasets.
- notebooks/: exploration and experiments.
- src/: reusable application and pipeline code.
- tests/: automated checks.
- docs/: system design and decision records.
- models/: trained model artifacts and metadata.