"""CLI behaviour, including CI-relevant exit codes."""

import contextlib
import io
import json

from pdfaudit.cli import main


def _run(args):
    """Run main(argv), capturing stdout. Returns (exit_code, stdout)."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = main(args)
    return code, buf.getvalue()


def test_scan_json_output(corpus):
    code, out = _run(["scan", corpus["box_over_text"], "--json"])
    data = json.loads(out)
    assert data["worst_severity"] == "critical"
    assert any(f["vector"] == "covered_text" for f in data["findings"])
    # default --fail-on is high; critical >= high -> exit 2
    assert code == 2


def test_clean_file_exits_zero(corpus):
    code, _ = _run(["scan", corpus["clean_stripped"], "--json"])
    assert code == 0


def test_fail_on_threshold_controls_exit_code(corpus):
    # clean_simple has only INFO findings.
    code_default, _ = _run(["scan", corpus["clean_simple"], "--json"])
    assert code_default == 0  # INFO < high

    code_info, _ = _run(["scan", corpus["clean_simple"], "--fail-on", "info", "--json"])
    assert code_info == 2  # INFO >= info threshold


def test_only_flag(corpus):
    code, out = _run(["scan", corpus["box_over_text"], "--only", "covered_text", "--json"])
    data = json.loads(out)
    assert {f["vector"] for f in data["findings"]} == {"covered_text"}


def test_unknown_vector_is_rejected(corpus):
    code, _ = _run(["scan", corpus["clean_simple"], "--only", "does_not_exist"])
    assert code == 1


def test_missing_file_errors_cleanly():
    code, _ = _run(["scan", "/no/such/file.pdf"])
    assert code == 1


def test_list_vectors(capsys):
    code = main(["list-vectors"])
    out = capsys.readouterr().out
    assert code == 0
    assert "revision_history" in out
    assert "covered_text" in out
