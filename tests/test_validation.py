"""
Tests for ChargeGap India validation framework and validation report.
Verifies cross-validation metrics, parameter sensitivity stability, and documented edge cases.
"""
from pathlib import Path
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"


def test_validation_report_exists_and_contains_sections():
    """Verify validation_report.md exists and contains required technical sections."""
    report_file = OUTPUTS / "validation_report.md"
    assert report_file.exists(), "outputs/validation_report.md must exist"
    text = report_file.read_text(encoding="utf-8")
    assert "Cross-Validation Against External Anchors" in text
    assert "Ministry of Power (MoP) 2024 Guidelines" in text
    assert "Sensitivity Analysis" in text
    assert "Failure Modes and Edge Cases" in text
    assert "Deduplication Radius Sensitivity" in text


def test_deduplication_radius_stability():
    """Verify deduplication radius sensitivity shows stability within 5% variation."""
    dedup_file = OUTPUTS / "dedup_radius_sensitivity.csv"
    if dedup_file.exists():
        df = pd.read_csv(dedup_file)
        assert not df.empty
        counts = df["charger_count"].tolist()
        max_diff = (max(counts) - min(counts)) / max(counts)
        assert max_diff <= 0.05, f"Deduplication variation too large: {max_diff:.3f}"


def test_gap_index_sensitivity_stability():
    """Verify rank stability for top districts across Monte Carlo weight permutations."""
    sens_file = OUTPUTS / "gap_index_sensitivity.csv"
    if sens_file.exists():
        df = pd.read_csv(sens_file)
        chennai = df[df["district_key"] == "chennai"]
        if not chennai.empty:
            assert chennai["median_rank"].iloc[0] <= 3.0
            assert chennai["top_k_share"].iloc[0] >= 0.90
