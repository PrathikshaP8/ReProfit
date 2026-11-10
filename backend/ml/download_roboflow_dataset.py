"""Download a pinned Roboflow dataset version without storing its API key.

Set ROBOFLOW_API_KEY in the environment, then pass the public workspace,
project, version, export format, and a new destination directory explicitly.
"""

from __future__ import annotations

import argparse
from importlib import import_module
import os
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--version", required=True, type=int)
    parser.add_argument(
        "--format",
        required=True,
        choices=("folder", "yolov8"),
        help="Use folder for image classification and yolov8 for detection exports",
    )
    parser.add_argument("--location", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    api_key = os.environ.get("ROBOFLOW_API_KEY")
    if not api_key:
        raise EnvironmentError("Set ROBOFLOW_API_KEY in the environment before downloading")
    if args.location.exists():
        raise FileExistsError(
            f"Refusing to download over an existing path: {args.location}. "
            "Choose a new destination to preserve existing datasets."
        )

    try:
        roboflow = import_module("roboflow")
    except ImportError as error:
        raise RuntimeError(
            "Roboflow SDK is required for downloads; install it with "
            "'python -m pip install roboflow'"
        ) from error

    project = (
        roboflow.Roboflow(api_key=api_key)
        .workspace(args.workspace)
        .project(args.project)
    )
    dataset = project.version(args.version).download(
        args.format,
        location=str(args.location),
    )
    print(f"Downloaded dataset to {dataset.location}")


if __name__ == "__main__":
    main()
