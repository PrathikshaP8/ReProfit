"""Securely download and validate the pinned ReProfit Roboflow datasets.

Run from an interactive terminal. The API key is entered through getpass,
passed only to each downloader subprocess via its environment, never written
to disk, and removed from the child environment after that download.
"""

from __future__ import annotations

import getpass
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys


BACKEND = Path(__file__).resolve().parents[1]
ML_DIR = BACKEND / "ml"
DOWNLOAD_SCRIPT = ML_DIR / "download_roboflow_dataset.py"

DATASETS = (
    {
        "label": "E waste data v13",
        "workspace": "electronic-waste-ni0o1",
        "project": "e-waste-data",
        "version": 13,
        "directory": ML_DIR / "datasets" / "roboflow_ewaste_v13",
        "validator": "train_product_detector_yolo11.py",
    },
    {
        "label": "Laptop screen damage v1",
        "workspace": "deeplearning-msmyh",
        "project": "laptop-screen-damage-detection-gzw1s",
        "version": 1,
        "directory": ML_DIR / "datasets" / "roboflow_laptop_screen_v1",
        "validator": "train_laptop_damage_yolo11.py",
    },
    {
        "label": "test-project v1 (known mobile labels)",
        "workspace": "laptop-damage-detection-trtwv",
        "project": "test-project-jrr6j",
        "version": 1,
        "directory": ML_DIR / "datasets" / "roboflow_test_project_v1",
        "validator": "train_laptop_damage_yolo11.py",
    },
    {
        "label": "Laptop Damage Identification v5",
        "workspace": "asset-damage-prediction",
        "project": "laptop_damage_identification",
        "version": 5,
        "directory": ML_DIR / "datasets" / "roboflow_laptop_damage_v5",
        "validator": "train_laptop_damage_yolo11.py",
    },
    {
        "label": "Balanced E-Waste v3",
        "workspace": "electronic-waste-detection",
        "project": "balanced-e-waste-dataset",
        "version": 3,
        "directory": ML_DIR / "datasets" / "roboflow_balanced_ewaste_v3",
        "validator": "train_product_detector_yolo11.py",
    },
    {
        "label": "electronic-waste-dataset v7",
        "workspace": "electronic-waste",
        "project": "electronic-waste-dataset",
        "version": 7,
        "directory": ML_DIR / "datasets" / "roboflow_ewaste_v7",
        "validator": "train_product_detector_yolo11.py",
    },
)


def _preflight() -> None:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise RuntimeError(
            "This setup must run in an interactive terminal so the API key "
            "can be entered through a hidden prompt."
        )
    missing = [
        package
        for package in ("roboflow", "yaml")
        if importlib.util.find_spec(package) is None
    ]
    if missing:
        raise RuntimeError(
            f"Missing Python packages: {', '.join(missing)}. "
            "Install them with: python -m pip install roboflow pyyaml"
        )
    existing = [dataset["directory"] for dataset in DATASETS if dataset["directory"].exists()]
    if existing:
        paths = "\n".join(f"  {path}" for path in existing)
        raise FileExistsError(
            "Refusing to download because these destinations already exist; "
            "nothing was changed:\n" + paths
        )


def _safe_output(output: str, api_key: str) -> str:
    output = output.replace(api_key, "[REDACTED]")
    output = re.sub(
        r"(?i)(api[_-]?key|api%5fkey|api%2dkey)(?:=|%3d)[^&\s\"']+",
        r"\1=[REDACTED]",
        output,
    )
    return output


def _run(command: list[str], *, api_key: str | None = None) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.pop("ROBOFLOW_API_KEY", None)
    if api_key is not None:
        environment["ROBOFLOW_API_KEY"] = api_key
    return subprocess.run(
        command,
        cwd=BACKEND,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def _report_failure(result: subprocess.CompletedProcess[str], api_key: str) -> None:
    output = _safe_output((result.stdout or "") + "\n" + (result.stderr or ""), api_key)
    if re.search(r"\b401\b|unauthori[sz]ed|invalid.{0,20}api.?key|api.?key.{0,30}(invalid|revoked)", output, re.I):
        print(
            "Roboflow authentication failed (HTTP 401 or invalid API key). "
            "Stopped immediately; no later datasets were attempted."
        )
        print("Create a replacement Private API Key in Roboflow Settings, then rerun this script.")
        return
    print(f"Command failed with exit code {result.returncode}.")
    lines = [line for line in output.splitlines() if line.strip()]
    if lines:
        print("\n".join(lines[-12:]))


def _download(dataset: dict[str, object], api_key: str) -> None:
    command = [
        sys.executable,
        str(DOWNLOAD_SCRIPT),
        "--workspace",
        str(dataset["workspace"]),
        "--project",
        str(dataset["project"]),
        "--version",
        str(dataset["version"]),
        "--format",
        "yolov8",
        "--location",
        str(dataset["directory"]),
    ]
    result = _run(command, api_key=api_key)
    if result.returncode:
        _report_failure(result, api_key)
        raise RuntimeError(f"Download failed for {dataset['label']}; remaining downloads stopped.")
    data_yaml = Path(dataset["directory"]) / "data.yaml"
    if not data_yaml.is_file():
        raise FileNotFoundError(
            f"Download returned success but the expected YOLO data.yaml is missing: {data_yaml}. "
            "No existing files were overwritten; inspect this partial download before rerunning."
        )
    print(f"Downloaded {dataset['label']} to {dataset['directory']}")
    if result.stdout.strip():
        print(_safe_output(result.stdout.strip(), api_key))


def _validate(dataset: dict[str, object]) -> bool:
    command = [
        sys.executable,
        str(ML_DIR / str(dataset["validator"])),
        "--data",
        str(Path(dataset["directory"]) / "data.yaml"),
        "--validate-only",
    ]
    result = _run(command)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.returncode == 0:
        return True
    if result.stderr.strip():
        print(result.stderr.strip())
    print(f"Validation failed for {dataset['label']} (exit {result.returncode}).")
    return False


def main() -> int:
    try:
        _preflight()
    except (RuntimeError, FileExistsError) as error:
        print(error, file=sys.stderr)
        return 2

    api_key = getpass.getpass("Enter your Roboflow Private API Key (input hidden): ").strip()
    if not api_key:
        print("No key was entered; nothing was downloaded.", file=sys.stderr)
        return 2

    try:
        for dataset in DATASETS:
            print(f"Downloading {dataset['label']}...")
            _download(dataset, api_key)
    except (RuntimeError, FileNotFoundError) as error:
        print(error, file=sys.stderr)
        return 1
    finally:
        api_key = ""

    print("\nRunning offline validation for each downloaded dataset...")
    failures = []
    for dataset in DATASETS:
        print(f"\nValidating {dataset['label']}...")
        if not _validate(dataset):
            failures.append(str(dataset["label"]))
    if failures:
        print("\nValidation failures: " + ", ".join(failures))
        return 1
    print("\nAll downloaded datasets passed their assigned validators.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
