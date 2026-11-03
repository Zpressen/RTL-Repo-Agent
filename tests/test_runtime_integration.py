import hashlib
import json
import sys
import subprocess

import pytest


def test_shared_runtime_protocol_imports_without_web_application():
    code = '''
import sys
from zerorepo.rtl_impl.process_events import JsonlProcessEventSink
from zerorepo.rtl_impl.rtl_artifacts import tree_manifest
from zerorepo.rtl_impl.runtime_integration import workbench_integration
assert not any(name.startswith("zerorepo.rtl_web") for name in sys.modules)
'''
    subprocess.run([sys.executable, "-c", code], check=True)


def test_hdl_fingerprint_keeps_existing_archive_format(tmp_path):
    from zerorepo.rtl_impl.rtl_artifacts import tree_manifest, RTLTreeError
    source = tmp_path / "dut.sv"
    source.write_text("module dut; endmodule\n")
    expected = [{"path": "dut.sv", "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                 "size_bytes": source.stat().st_size}]
    payload = json.dumps(expected, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert tree_manifest(tmp_path) == (hashlib.sha256(payload.encode()).hexdigest(), expected)
    (tmp_path / "link.sv").symlink_to(source)
    with pytest.raises(RTLTreeError, match="符号链接"):
        tree_manifest(tmp_path)


def test_workbench_requires_explicit_installed_application(monkeypatch):
    from zerorepo.rtl_impl import runtime_integration
    monkeypatch.setattr(runtime_integration, "entry_points", lambda **kwargs: [])
    with pytest.raises(RuntimeError, match="installed RTL Studio"):
        runtime_integration.workbench_integration()
