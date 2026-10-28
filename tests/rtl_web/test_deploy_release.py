from pathlib import Path
import importlib.util
import json
import pytest

spec = importlib.util.spec_from_file_location(
    "release", Path(__file__).resolve().parents[2] / "scripts/rtl_demo/release.py"
)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def dist(root, text):
    root.mkdir()
    (root / "index.html").write_text(text)
    (root / "assets").mkdir()
    (root / "assets" / f"{text}.js").write_text(text)
    (root / "cases/e203").mkdir(parents=True)
    (root / "cases/e203/manifest.json").write_text(json.dumps({"bundle_id": text}))
    (root / "cases/aes_cipher_system_hard").mkdir()
    (root / "cases/aes_cipher_system_hard/manifest.json").write_text(
        json.dumps({"bundle_id": "aes-" + text})
    )
    (root / "cases/index.json").write_text(
        json.dumps(
            {"cases": [{"case_id": "e203"}, {"case_id": "aes_cipher_system_hard"}]}
        )
    )
    return root


def test_design_only_atomic_publish_backup_and_rollback(tmp_path):
    base = tmp_path / "srv"
    (base / "main").mkdir(parents=True)
    (base / "main/index.html").write_text("keep-main")
    old = dist(base / "design", "old")
    new = dist(tmp_path / "dist", "new")
    stage = tmp_path / "releases"
    release.stage(new, stage, "v1")
    src = stage / "v1/design"
    release.install(src, base=base, dry_run=True, test_root=True)
    assert (old / "index.html").read_text() == "old"
    result = release.install(src, base=base, test_root=True)
    assert (old / "index.html").read_text() == "new"
    assert (
        json.loads((old / "cases/aes_cipher_system_hard/manifest.json").read_text())[
            "bundle_id"
        ]
        == "aes-new"
    )
    assert (old / "assets/old.js").is_file()
    release.install(Path(result["backup"]), base=base, test_root=True, rollback=True)
    assert (old / "index.html").read_text() == "old"
    assert (
        json.loads((old / "cases/aes_cipher_system_hard/manifest.json").read_text())[
            "bundle_id"
        ]
        == "aes-old"
    )
    assert (old / "assets/new.js").is_file()
    assert (base / "main/index.html").read_text() == "keep-main"


def test_reject_tamper_and_symlink(tmp_path):
    d = dist(tmp_path / "dist", "new")
    stage = tmp_path / "releases"
    release.stage(d, stage, "v1")
    src = stage / "v1/design"
    (src / "index.html").write_text("tampered")
    with pytest.raises(ValueError, match="mismatch"):
        release.install(src, base=tmp_path / "srv", test_root=True)
    (d / "leak.json").symlink_to(d / "cases/e203/manifest.json")
    with pytest.raises(ValueError, match="Symlink"):
        release.stage(d, stage, "v2")
