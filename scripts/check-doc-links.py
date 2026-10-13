"""Check local inline Markdown file targets, excluding ignored files, URLs and anchors."""

import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    files = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT,
        )
        .decode()
        .split("\0")
    )
    errors = []
    for name in sorted(set(files)):
        path = ROOT / name
        if path.suffix != ".md" or not path.is_file():
            continue
        source = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
        for target in re.findall(r"\]\((<[^>]+>|[^\s)]+)(?:\s+\"[^\"]*\")?\)", source):
            target = target.strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            if not (path.parent / unquote(parsed.path)).exists():
                errors.append(f"{name}: missing {target}")
    print("\n".join(errors) if errors else "Local Markdown file links passed.")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
