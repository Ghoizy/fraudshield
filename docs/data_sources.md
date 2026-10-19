# Data Sources and Attribution

## Dataset origin

FraudShield uses synthetic transaction data published by the
Fraud Detection Handbook project.

The dataset was obtained from the upstream project.
FraudShield does not claim authorship of the dataset.

Simulator documentation:
https://fraud-detection-handbook.github.io/fraud-detection-handbook/Chapter_3_GettingStarted/SimulatedDataset.html

Dataset repository:
https://github.com/Fraud-Detection-Handbook/simulated-data-raw

## Version used

Upstream commit:
`6e67dbd0a3bfe0d7ec33abc4bce5f37cd4ff0d6a`

Experiment period:
April 1–30, 2018.

All 30 local daily files matched the upstream files
using SHA-256 verification.

Evidence:
[Dataset source verification](../reports/dataset_source_verification.json)

Download instructions:
[Reproduction guide](reproduction.md#download-the-verified-dataset)

## License information

The handbook website identifies:
- GNU GPL v3.0 for its code.
- CC BY-SA 4.0 for its prose and pictures.

An explicit license covering the raw dataset files has not
been confirmed in this project's review.

The handbook's code and content notices are recorded here
without assuming that either automatically covers the dataset.

Raw datasets and trained model artifacts are excluded from
this Git repository. Download instructions point to the
upstream source.

This attribution note does not grant rights to upstream material
or define a license for FraudShield's own code.

## Interpretation of results

The data is synthetic. Evaluation results describe performance
on this simulation and the documented time period.

They do not establish performance on real payment transactions.
