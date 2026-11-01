"""Export the final one-step migration for an authenticated operator SQL editor."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db.migrate import sql_editor_upgrade  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--release", required=True)
parser.add_argument("--from-revision", required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
args.output.write_text(sql_editor_upgrade(args.release, args.from_revision), encoding="utf-8")
print("Exported guarded operator SQL; no database connection or credential was used.")
