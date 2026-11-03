#!/usr/bin/env python3
"""
Model Evaluation Script for BIT-PLATE-CV-1.0
Evaluates the official frozen computer vision model against the complete 60-image sample set.
Calculates Confusion Matrix, True Positives, True Negatives, False Positives, False Negatives,
and Defect Recall according to Round 2 specifications.
"""

import os
import sys
import csv
import json
from pathlib import Path

# Add project root and Model directory to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_DIR = PROJECT_ROOT / "Model"
SAMPLES_DIR = PROJECT_ROOT / "Samples"
sys.path.insert(0, str(MODEL_DIR))

try:
    from inference import predict, MODEL_VERSION
except ImportError:
    # Try importing from current directory if run from root
    from Model.inference import predict, MODEL_VERSION


def evaluate():
    labels_file = SAMPLES_DIR / "labels.csv"
    if not labels_file.exists():
        print(f"Error: labels file not found at {labels_file}", file=sys.stderr)
        sys.exit(1)

    with open(labels_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        samples = list(reader)

    total_samples = len(samples)
    successful_predictions = 0
    failed_predictions = 0

    # Metrics counters:
    # Positive class = Defective, Negative class = Normal
    # Rows = Actual (Normal, Defective), Columns = Predicted (Normal, Defective)
    # Confusion matrix layout:
    #                 Predicted Normal    Predicted Defective
    # Actual Normal          TN                   FP
    # Actual Defective       FN                   TP
    tn = 0  # Actual Normal, Predicted Normal
    fp = 0  # Actual Normal, Predicted Defective
    fn = 0  # Actual Defective, Predicted Normal
    tp = 0  # Actual Defective, Predicted Defective

    results_detail = []

    for item in samples:
        rel_path = item["relative_path"]
        actual_label = item["label"].strip()
        image_path = SAMPLES_DIR / rel_path

        if not image_path.exists():
            failed_predictions += 1
            results_detail.append({
                "file": rel_path,
                "actual": actual_label,
                "predicted": None,
                "status": "MISSING_FILE",
                "confidence": None,
                "defect_prob": None
            })
            continue

        try:
            pred = predict(str(image_path), model_path=str(MODEL_DIR / "classifier.npz"))
            pred_class = pred["predicted_class"]
            conf = pred["confidence"]
            defect_prob = pred["defect_probability"]
            successful_predictions += 1

            if actual_label == "Normal":
                if pred_class == "Normal":
                    tn += 1
                else:
                    fp += 1
            elif actual_label == "Defective":
                if pred_class == "Defective":
                    tp += 1
                else:
                    fn += 1

            results_detail.append({
                "file": rel_path,
                "actual": actual_label,
                "predicted": pred_class,
                "status": "SUCCESS",
                "confidence": conf,
                "defect_prob": defect_prob
            })
        except Exception as e:
            failed_predictions += 1
            results_detail.append({
                "file": rel_path,
                "actual": actual_label,
                "predicted": None,
                "status": f"ERROR: {str(e)}",
                "confidence": None,
                "defect_prob": None
            })

    # Calculations
    defect_recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    accuracy = (tp + tn) / total_samples if total_samples > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    f1_score = 2 * (precision * defect_recall) / (precision + defect_recall) if (precision + defect_recall) > 0 else 0.0

    report = {
        "model_version": MODEL_VERSION,
        "total_samples": total_samples,
        "successful_predictions": successful_predictions,
        "failed_predictions": failed_predictions,
        "confusion_matrix": {
            "matrix": [
                [tn, fp],  # Actual Normal: [Pred Normal (TN), Pred Defective (FP)]
                [fn, tp],  # Actual Defective: [Pred Normal (FN), Pred Defective (TP)]
            ],
            "row_labels": ["Actual Normal", "Actual Defective"],
            "col_labels": ["Predicted Normal", "Predicted Defective"],
        },
        "counts": {
            "true_positives (TP)": tp,
            "true_negatives (TN)": tn,
            "false_positives (FP)": fp,
            "false_negatives (FN)": fn,
        },
        "metrics": {
            "defect_recall": defect_recall,
            "defect_recall_percent": f"{defect_recall * 100:.2f}%",
            "accuracy": accuracy,
            "accuracy_percent": f"{accuracy * 100:.2f}%",
            "precision": precision,
            "precision_percent": f"{precision * 100:.2f}%",
            "f1_score": f1_score,
        },
        "limitations": (
            "Evaluated on 60 synthetic procedural illustrations under fixed framing and lighting. "
            "No real factory photos or domain shifts were present. Scores are uncalibrated model outputs."
        )
    }

    # Print Formatted Report to stdout
    print("=" * 70)
    print(" ROUND 2 AI QUALITY INSPECTION — MODEL EVALUATION REPORT")
    print("=" * 70)
    print(f"Model Identifier      : {MODEL_VERSION}")
    print(f"Total Sample Count    : {total_samples}")
    print(f"Successful Predictions: {successful_predictions}")
    print(f"Failed Predictions    : {failed_predictions}")
    print("-" * 70)
    print("CONFUSION MATRIX:")
    print("                     Predicted Normal    Predicted Defective    Total")
    print(f"  Actual Normal            {tn:4d}                {fp:4d}              {tn + fp:4d}")
    print(f"  Actual Defective         {fn:4d}                {tp:4d}              {fn + tp:4d}")
    print(f"  Total                    {tn + fn:4d}                {fp + tp:4d}              {total_samples:4d}")
    print("-" * 70)
    print("CLASSIFICATION COUNTS:")
    print(f"  True Positives  (TP) : {tp}  (Actual Defective, Predicted Defective)")
    print(f"  True Negatives  (TN) : {tn}  (Actual Normal, Predicted Normal)")
    print(f"  False Positives (FP) : {fp}  (Actual Normal, Predicted Defective)")
    print(f"  False Negatives (FN) : {fn}  (Actual Defective, Predicted Normal)")
    print("-" * 70)
    print("PERFORMANCE METRICS:")
    print(f"  Defect Recall (TP / (TP + FN)) : {defect_recall:.4f} ({defect_recall * 100:.2f}%)")
    print(f"  Precision    (TP / (TP + FP)) : {precision:.4f} ({precision * 100:.2f}%)")
    print(f"  Accuracy                       : {accuracy:.4f} ({accuracy * 100:.2f}%)")
    print(f"  F1-Score                       : {f1_score:.4f}")
    print("-" * 70)
    print("LIMITATIONS:")
    print(f"  {report['limitations']}")
    print("=" * 70)

    # Save JSON report
    report_file = PROJECT_ROOT / "backend" / "scripts" / "evaluation_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Report saved to: {report_file}")

    return report


if __name__ == "__main__":
    evaluate()

