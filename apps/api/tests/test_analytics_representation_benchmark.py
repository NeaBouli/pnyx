"""The benchmark must reject comparing the aggregate implementation to itself."""
from pathlib import Path
import subprocess
import sys


def test_benchmark_rejects_aggregate_as_original_baseline(tmp_path: Path) -> None:
    baseline = tmp_path / "incorrect-baseline.py"
    baseline.write_text("from routers.analytics import compute_cumulative_representation\n")
    api_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(api_root / "tests/benchmark_analytics_representation.py"), str(baseline)],
        cwd=api_root, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode != 0
    assert "Baseline must be the original function from PR #681's base commit" in result.stderr
