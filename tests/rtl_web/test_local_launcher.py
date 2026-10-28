import os
from pathlib import Path
import subprocess
import sys
import pytest
from zerorepo.rtl_web.local import environment_file, stop


def test_env_file_loads_values_without_executing_shell(tmp_path):
    marker = tmp_path / "must-not-exist"
    path = tmp_path / "runtime.env"
    path.write_text(f"""# comment
export ZEROREPO_API_KEY="test key"
LITERAL=$(touch {marker})
EMPTY=
""")
    values = environment_file(path)
    assert values["ZEROREPO_API_KEY"] == "test key" and values["EMPTY"] == ""
    assert values["LITERAL"].startswith("$(touch") and not marker.exists()
    path.write_text("ZEROREPO_API_KEY='private-value\n")
    with pytest.raises(ValueError) as error:
        environment_file(path)
    assert "private-value" not in str(error.value)


def test_launcher_cleanup_terminates_only_started_services():
    own = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True
    )
    other = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True
    )
    try:
        stop([own])
        assert own.poll() is not None and other.poll() is None
    finally:
        stop([own, other])
