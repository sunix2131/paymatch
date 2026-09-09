from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from payment_reconciliation.config import load_rules
from payment_reconciliation.domain import Source
from payment_reconciliation.engine import reconcile
from payment_reconciliation.loaders import load_transactions
from payment_reconciliation.storage import save_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reconcile",
        description="Reconcile internal transactions against a bank or PSP statement.",
    )
    parser.add_argument("internal", type=Path, help="internal .csv or .json file")
    parser.add_argument("external", type=Path, help="external .csv or .json file")
    parser.add_argument("--rules", required=True, type=Path, help="matching rules YAML")
    parser.add_argument("--output", type=Path, help="write JSON report instead of stdout")
    parser.add_argument(
        "--database-url",
        help="optionally persist the run through SQLAlchemy (PostgreSQL recommended)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.output:
            for source in (args.internal, args.external, args.rules):
                if args.output.resolve() == source.resolve() or (
                    args.output.exists() and args.output.samefile(source)
                ):
                    raise ValueError("output must not overwrite an input or rules file")
        rules = load_rules(args.rules)
        internal = load_transactions(args.internal, Source.INTERNAL)
        external = load_transactions(args.external, Source.EXTERNAL)
        report = reconcile(internal, external, rules)
        payload = report.as_dict()
        if args.database_url:
            payload["run_id"] = save_report(
                args.database_url,
                report,
                rules,
                args.internal,
                args.external,
            )
        rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            _write_report(args.output, rendered)
        else:
            sys.stdout.write(rendered)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


def _write_report(path: Path, rendered: str) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
