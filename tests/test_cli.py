from __future__ import annotations

import json
from pathlib import Path

import pytest

from payment_reconciliation.cli import main


def test_output_cannot_overwrite_source(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "payments.json"
    source.write_text("[]", encoding="utf-8")
    rules = tmp_path / "rules.yaml"
    rules.write_text("rules: []", encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        main([str(source), str(source), "--rules", str(rules), "--output", str(source)])
    assert error.value.code == 2
    assert source.read_text() == "[]"
    assert "must not overwrite" in capsys.readouterr().err


def test_unwritable_output_is_a_cli_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = Path(__file__).parents[1]
    with pytest.raises(SystemExit) as error:
        main(
            [
                str(project / "examples/internal.csv"),
                str(project / "examples/external.csv"),
                "--rules",
                str(project / "examples/rules.yaml"),
                "--output",
                str(tmp_path / "missing" / "report.json"),
            ]
        )
    assert error.value.code == 2
    assert "Traceback" not in capsys.readouterr().err


def test_example_cli_report(tmp_path: Path) -> None:
    project = Path(__file__).parents[1]
    output = tmp_path / "report.json"

    exit_code = main(
        [
            str(project / "examples/internal.csv"),
            str(project / "examples/external.csv"),
            "--rules",
            str(project / "examples/rules.yaml"),
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["summary"]["MATCHED"] == 1
    assert payload["summary"]["AMOUNT_MISMATCH"] == 1
    assert payload["summary"]["MISSING_EXTERNAL"] == 1
    assert payload["summary"]["MISSING_INTERNAL"] == 1
