from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hangeul_core.live_regression import build_windows_live_artifact, validate_windows_live_artifact



def _cmd_create(args: argparse.Namespace) -> int:
    payload = build_windows_live_artifact(args.flow)
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(path)
    return 0



def _cmd_validate(args: argparse.Namespace) -> int:
    payload = json.loads(Path(args.path).read_text(encoding="utf-8"))
    report = validate_windows_live_artifact(payload)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1



def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create or validate Windows live regression artifacts.")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="Write a regression-artifact template JSON file.")
    create.add_argument("--flow", choices=["exact_path", "current_document"], required=True)
    create.add_argument("--out", required=True)
    create.set_defaults(func=_cmd_create)

    validate = sub.add_parser("validate", help="Validate a captured regression-artifact JSON file.")
    validate.add_argument("--path", required=True)
    validate.set_defaults(func=_cmd_validate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
