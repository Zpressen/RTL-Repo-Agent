"""Deterministic evidence projections shared by Stage4 and the gate."""
import re

SPEC_MAPPING_POLICY_VERSION = "complete_interface_tables_v2"


def interface_evidence(registry, contract, source_file):
    """Select complete original tables, including tables split by the index."""
    from pathlib import Path
    from ..schemas import SourceEvidence
    from ..utils import markdown_ports, interface_contract_errors
    ports = {port.name: port for port in getattr(contract, "ports", [])}
    if not ports:
        return []
    paths = {str(Path(ref.source_md_file).resolve()) for ref in getattr(contract, "text_grounding", [])
             if ref.source_md_file}
    if not paths:
        paths = {str(Path(source_file).resolve())}
    refs = []
    for path in sorted(paths):
        text = registry.documents.get(path)
        if text is None:
            raise ValueError(f"Authoritative interface source is outside readable input specifications: {path}")
        lines = text.splitlines(keepends=True)
        index, fence = 0, None
        while index < len(lines):
            marker = re.match(r"^\s*(`{3,}|~{3,})", lines[index])
            if marker:
                if fence is None:
                    fence = marker[1][0]
                elif marker[1][0] == fence:
                    fence = None
            if fence is not None or "|" not in lines[index]:
                index += 1
                continue
            start = index
            while index < len(lines) and "|" in lines[index]:
                index += 1
            quote = "".join(lines[start:index]).rstrip("\n")
            actual = markdown_ports(quote)
            names = {port.name for port in actual}
            # A shared clk/rst in another module's table is not sufficient.
            if not names or not names <= set(ports):
                continue
            errors = interface_contract_errors(actual, [ports[name] for name in ports if name in names],
                                               label="authoritative interface source")
            if errors:
                raise ValueError("; ".join(errors))
            ref = SourceEvidence(source_file=path, quote=quote, start_line=start + 1,
                                 end_line=start + 1 + quote.count("\n"))
            identity = registry.register(ref)
            refs.append(registry.entries[identity].model_dump())
    return refs


def module_spec_blocks(export, context, bundle, registry):
    """Rebuild exact evidence text and its complete S-block mapping."""
    from ..schemas import SpecBlock, ModuleSpecBlocks
    from ..utils import split_spec_blocks
    module_name = export.module
    export = export.model_dump()
    refs = [ref for group in ("responsibilities", "constraints") for r in context[group] for ref in r["source_refs"]]
    refs.extend(ref for o in export["behavioral_obligations"] for ref in o["source_refs"])
    # Include the authoritative interface text; it supports declarations,
    # not every behavioral task. State evidence is retained as well.
    owned_states = {a["state_id"] for r in context["responsibilities"] for a in r["state_accesses"]}
    refs.extend(ref for state in context["state_objects"] if state["state_id"] in owned_states for ref in state["source_refs"])
    integration_ids = set()
    if any(block["block_kind"] == "inst" for block in export["structural_blocks"]):
        refs.extend(context.get("boundary_source_refs", []))
        integration_ids = {registry.register(ref) for ref in context.get("boundary_source_refs", [])}
    declaration_ids = {registry.register(ref) for state in context["state_objects"] if state["state_id"] in owned_states for ref in state["source_refs"]}
    contract = getattr(bundle, "interface_contract", None)
    for ref in interface_evidence(registry, contract, export["source_refs"]["module_spec_file"]):
        refs.append(ref)
        declaration_ids.add(registry.register(ref))
    unique = {registry.register(ref): ref for ref in refs}
    entries = sorted(unique.items(), key=lambda pair: (pair[1]["source_file"], pair[1]["start_line"], pair[1]["end_line"], pair[0]))
    blocks = []
    for identity, ref in entries:
        # Preserve each complete verified excerpt. Longer excerpts can
        # map to multiple S blocks without losing their shared EV ID.
        for chunk in split_spec_blocks(ref["quote"]):
            text = chunk.text if hasattr(chunk, "text") else chunk.get("text", "")
            blocks.append(SpecBlock(block_id=f"S{len(blocks)+1:03d}", text=text,
                                    source_evidence_ids=[identity], declaration_support=identity in declaration_ids,
                                    integration_support=identity in integration_ids))
    return ModuleSpecBlocks(module=module_name, source_spec_file=export["source_refs"]["module_spec_file"], blocks=blocks)
