"""Run the whole FinSight pipeline end to end, in order.

Each step is an independent module; this just calls them in sequence so the
project is reproducible with one command:

    python src/run_pipeline.py
"""
from __future__ import annotations

import generate_data
import data_quality
import clean_data
import load_db
import segmentation
import campaign_analytics
import anomaly_detection
import recommendation
import build_metrics
import ai_insights
import export_powerbi

STEPS = [
    ("Generate synthetic data (+ inject defects)", generate_data.main),
    ("Data-quality checks", data_quality.main),
    ("Clean data", clean_data.main),
    ("Load SQLite database", load_db.load),
    ("RFM segmentation", segmentation.main),
    ("Campaign analytics", campaign_analytics.main),
    ("Anomaly detection", anomaly_detection.main),
    ("Next-best-category recommendations", recommendation.main),
    ("Build verified metrics", build_metrics.main),
    ("AI business summary", ai_insights.main),
    ("Export Power BI CSVs", export_powerbi.main),
]


def main() -> None:
    for i, (label, fn) in enumerate(STEPS, 1):
        print("\n" + "=" * 70)
        print(f"STEP {i}/{len(STEPS)}: {label}")
        print("=" * 70)
        fn()
    print("\nPipeline complete. See outputs/ and outputs/powerbi/.")
    print("Build the Excel workbook separately with:  python excel/build_excel.py")


if __name__ == "__main__":
    main()
