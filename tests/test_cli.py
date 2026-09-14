from evey2obs import __version__
from evey2obs.cli import main


def test_version_is_defined() -> None:
    assert __version__ == "0.1.0"


def test_doctor_reports_ready(capsys) -> None:
    assert main(["doctor"]) == 0
    output = capsys.readouterr().out
    assert "project scaffold is ready" in output


def test_acceptance_report_cli(capsys) -> None:
    code = main(["acceptance-report", "docs/samples/real_samples.example.json"])
    assert code == 0
    output = capsys.readouterr().out
    assert '"complete": true' in output


def test_cache_clear_cli(capsys) -> None:
    code = main(["cache-clear"])
    assert code == 0
    output = capsys.readouterr().out
    assert "转写缓存" in output

