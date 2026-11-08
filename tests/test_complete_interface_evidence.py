"""Declarations retain all source port tables, even across evidence cuts."""
from types import SimpleNamespace

import pytest

from zerorepo.rtl_impl.module_planner.utils.evidence import EvidenceRegistry
from zerorepo.rtl_impl.module_planner.utils.spec_mapping import interface_evidence, module_spec_blocks
from zerorepo.rtl_impl.port_contracts import markdown_ports


def fixture(tmp_path):
    path = tmp_path / "top.md"
    tables = []
    for group in range(2):
        tables.append("| Name | Direction | Width | Description |\n| --- | --- | --- | --- |\n" + "".join(
            f"| port_{group}_{i} | input | 32 | Long description of this input signal and its role. |\n" for i in range(50)))
    path.write_text("# Top\n\n## Inputs\n\n" + tables[0] + "\n## More inputs\n\n" + tables[1] + "\n## Unrelated\nUNRELATED_SENTINEL\n")
    other = tmp_path / "other.md"
    other.write_text("| Name | Direction | Width |\n| --- | --- | --- |\n| port_0_0 | input | 32 |\n| foreign | output | 1 |\n")
    inputs = SimpleNamespace(source_specs=[SimpleNamespace(path=str(p), markdown=p.read_text()) for p in [path, other]])
    registry = EvidenceRegistry(inputs)
    ports = [SimpleNamespace(name=f"port_{g}_{i}", direction="input", width="32") for g in range(2) for i in range(50)]
    return path, registry, SimpleNamespace(ports=ports, text_grounding=[])


def test_all_interface_tables_survive_index_splits_and_stay_declaration_support(tmp_path):
    path, registry, contract = fixture(tmp_path)
    assert len(registry.entries) > 4  # Both original tables cross index boundaries.
    export = {"module": "top", "source_refs": {"module_spec_file": str(path)},
              "structural_blocks": [{"block_kind": "decl"}], "behavioral_obligations": []}
    view = SimpleNamespace(module="top", model_dump=lambda: export)
    context = {"responsibilities": [], "constraints": [], "state_objects": []}
    blocks = module_spec_blocks(view, context, SimpleNamespace(interface_contract=contract), registry)
    text = "\n\n".join(block.text for block in blocks.blocks)
    assert {p.name for p in markdown_ports(text)} == {p.name for p in contract.ports}
    assert all(block.declaration_support for block in blocks.blocks)
    assert "UNRELATED_SENTINEL" not in text and "foreign" not in text
    for block in blocks.blocks:
        for identity in block.source_evidence_ids:
            assert registry.entries[identity].source_file == str(path)
            assert registry.entries[identity].start_line and registry.entries[identity].content_hash


def test_original_interface_direction_and_width_are_still_checked(tmp_path):
    path, registry, contract = fixture(tmp_path)
    contract.ports[0].width = "16"
    with pytest.raises(ValueError, match="width must be 16"):
        interface_evidence(registry, contract, str(path))


def test_interface_evidence_cannot_come_from_outside_input_sources(tmp_path):
    path, registry, contract = fixture(tmp_path)
    contract.text_grounding = [SimpleNamespace(source_md_file=str(tmp_path / "unknown.md"))]
    with pytest.raises(ValueError, match="outside readable input"):
        interface_evidence(registry, contract, str(path))
