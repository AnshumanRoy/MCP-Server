"""Download the Olist Brazilian E-Commerce dataset via the Kaggle API.

Requires Kaggle credentials:
  - Set KAGGLE_USERNAME and KAGGLE_KEY env vars, OR
  - Place kaggle.json at ~/.kaggle/kaggle.json

Usage:
    python scripts/download_data.py [--data-dir ./data] [--force]

After downloading, run:
    python scripts/load_data.py --data-dir ./data --reset
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dotenv optional fallback
    load_dotenv = None

DATASET = "olistbr/brazilian-ecommerce"
DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def check_kaggle_cli() -> None:
    if shutil.which("kaggle") is None:
        print(
            "ERROR: kaggle CLI not found. Install it with: pip install kaggle",
            file=sys.stderr,
        )
        sys.exit(1)


def check_credentials() -> None:
    if os.getenv("KAGGLE_USERNAME") and os.getenv("KAGGLE_KEY"):
        return
    kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
    if kaggle_json.exists():
        return
    print(
        "ERROR: Kaggle credentials not found. Set KAGGLE_USERNAME and KAGGLE_KEY "
        "env vars, or place kaggle.json at ~/.kaggle/kaggle.json "
        "(get it from Kaggle → Account → API → Create New API Token).",
        file=sys.stderr,
    )
    sys.exit(1)


def download(data_dir: Path, force: bool) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "kaggle",
        "datasets",
        "download",
        "-d",
        DATASET,
        "-p",
        str(data_dir),
        "--unzip",
    ]
    if force:
        cmd.append("--force")

    print(f"Downloading {DATASET} into {data_dir.resolve()} ...")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: kaggle download failed (exit {exc.returncode})", file=sys.stderr)
        sys.exit(exc.returncode)

    zips = list(data_dir.glob("*.zip"))
    for z in zips:
        z.unlink()
        print(f"  removed {z.name}")

    print("Download complete.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        default=str(DEFAULT_DATA_DIR),
        help="Directory to download CSVs into (default: ./data)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download even if files exist",
    )
    args = parser.parse_args()

    # Load .env early so credentials are available for checks/downloads.
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if load_dotenv is not None and env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)

    check_kaggle_cli()
    check_credentials()
    download(Path(args.data_dir), args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
