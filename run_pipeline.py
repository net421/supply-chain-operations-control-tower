"""Run the complete local control-tower evidence pipeline with one command."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent

PIPELINE_STEPS = (
    ("generate deterministic source data", "data/generate_synthetic_data.py"),
    ("calculate Python KPIs", "python/calculate_kpis.py"),
    ("reconcile DuckDB SQL with Python", "validation/reconcile_sql_python.py"),
    ("validate sources and outputs", "validation/validate_outputs.py"),
)


def run_command(label: str, command: list[str]) -> None:
    print(f"\n==> {label}", flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--with-tests",
        action="store_true",
        help="Run pytest after the data pipeline and reconciliation succeed.",
    )
    args = parser.parse_args()

    for label, relative_script in PIPELINE_STEPS:
        run_command(label, [sys.executable, str(ROOT / relative_script)])
    if args.with_tests:
        run_command("run automated tests", [sys.executable, "-m", "pytest", "-q"])
    print("\nControl tower pipeline completed successfully.")


if __name__ == "__main__":
    main()
