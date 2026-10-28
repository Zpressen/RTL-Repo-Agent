from pathlib import Path
import pytest
import yaml
from zerorepo.rtl_web.settings import Settings
from zerorepo.rtl_web.store import Store

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def settings(tmp_path):
    path = tmp_path / "demo.yaml"
    cfg = yaml.safe_load((REPO / "configs/rtl_demo.example.yaml").read_text())
    cfg.update(repo_root=str(REPO), data_root=str(tmp_path / "state"), development=True)
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True))
    return Settings(path)


@pytest.fixture
def ledger(settings):
    return Store(settings.data)


@pytest.fixture
def bundle(settings, ledger):
    from zerorepo.rtl_web.import_case import import_case

    if not settings.source.is_dir():
        pytest.skip("Local E203 artifacts absent; portable unit tests still run.")
    return import_case(settings, ledger)
