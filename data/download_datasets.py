"""
Download Walmart datasets from Kaggle.

Required credentials (any one):
  - ~/.kaggle/kaggle.json   ({"username": "...", "key": "..."})
  - KAGGLE_USERNAME + KAGGLE_KEY env vars

Datasets downloaded:
  - m5-forecasting-accuracy        (42k products × 10 stores × 1941 days)
  - walmart-recruiting-store-sales-forecasting  (weekly store sales + features)
"""
import os
import json
import zipfile
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

RAW_DIR = Path(__file__).parent / "raw"

COMPETITIONS = [
    "m5-forecasting-accuracy",
    "walmart-recruiting-store-sales-forecasting",
]


def _ensure_kaggle_credentials():
    kaggle_dir = Path.home() / ".kaggle"
    kaggle_json = kaggle_dir / "kaggle.json"

    if kaggle_json.exists():
        return

    username = os.getenv("KAGGLE_USERNAME")
    key = os.getenv("KAGGLE_KEY")
    if not username or not key:
        raise EnvironmentError(
            "Kaggle credentials not found.\n"
            "Either place kaggle.json in ~/.kaggle/ or set "
            "KAGGLE_USERNAME and KAGGLE_KEY environment variables."
        )

    kaggle_dir.mkdir(parents=True, exist_ok=True)
    kaggle_json.write_text(json.dumps({"username": username, "key": key}))
    kaggle_json.chmod(0o600)
    print(f"Kaggle credentials written to {kaggle_json}")


def _unzip_all(directory: Path):
    for zip_path in list(directory.glob("*.zip")):
        print(f"  Extracting {zip_path.name} ...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(directory)
        zip_path.unlink()


def download_competition(competition: str):
    import kaggle  # imported here so the module import itself doesn't fail without kaggle installed

    dest = RAW_DIR / competition
    if dest.exists() and any(dest.iterdir()):
        print(f"Skipping '{competition}' — already present at {dest}")
        return

    dest.mkdir(parents=True, exist_ok=True)
    print(f"Downloading competition: {competition} ...")
    try:
        kaggle.api.competition_download_files(competition, path=str(dest), quiet=False)
    except Exception as e:
        if "403" in str(e) or "Forbidden" in str(e):
            raise SystemExit(
                f"\n[403 Forbidden] Cannot download '{competition}'.\n\n"
                "You must accept the competition rules on Kaggle before the API works:\n"
                f"  https://www.kaggle.com/competitions/{competition}/rules\n\n"
                "1. Open the link above, scroll down, and click 'I Understand and Accept'.\n"
                "2. Re-run this script.\n"
            ) from None
        raise

    _unzip_all(dest)
    # Some competitions nest another zip layer
    _unzip_all(dest)
    print(f"  Saved to {dest.resolve()}")


def main():
    _ensure_kaggle_credentials()
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    for comp in COMPETITIONS:
        download_competition(comp)

    print(f"\nAll datasets available under {RAW_DIR.resolve()}")


if __name__ == "__main__":
    main()
