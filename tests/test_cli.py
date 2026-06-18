from evey2obs import __version__
from evey2obs.cli import main


def test_version_is_defined() -> None:
    assert __version__ == "0.1.0"


def test_doctor_reports_ready(capsys) -> None:
    assert main(["doctor"]) == 0
    output = capsys.readouterr().out
    assert "project scaffold is ready" in output
