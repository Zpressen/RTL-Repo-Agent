from __future__ import annotations

from collections import Counter
from typing import Dict, Iterable

from ..schemas import (
    ArchitectureTimingContractArtifact,
    GlobalTemporalFactsArtifact,
    ModuleSkeletonExport,
    ModuleTimingBindingArtifact,
    Stage2RepoSkeletonArtifact,
    TimingBindingCheckArtifact,
    TimingBindingIssue,
)


def check_temporal_bindings(
    *,
    task_id: str,
    temporal_facts: GlobalTemporalFactsArtifact,
    repo_skeleton: Stage2RepoSkeletonArtifact,
    architecture: ArchitectureTimingContractArtifact,
    skeletons: Dict[str, ModuleSkeletonExport],
    bindings: Dict[str, ModuleTimingBindingArtifact],
    input_fingerprint: str = "",
) -> TimingBindingCheckArtifact:
    issues: list[TimingBindingIssue] = []

    def add(
        code: str,
        severity: str,
        message: str,
        *,
        module: str = "",
        block_id: str = "",
        obligation_id: str = "",
    ) -> None:
        issues.append(
            TimingBindingIssue(
                code=code,
                severity=severity,
                module=module,
                block_id=block_id,
                obligation_id=obligation_id,
                message=message,
            )
        )

    expected_modules = list(repo_skeleton.planning_decisions.generation_order) or [
        item.module for item in repo_skeleton.modules
    ]
    if architecture.module_set != expected_modules:
        add(
            "ARCHITECTURE_MODULE_SET_DRIFT",
            "ERROR",
            f"Architecture timing module_set {architecture.module_set} does not match Stage2 modules {expected_modules}.",
        )

    for item in temporal_facts.unsupported_features:
        lowered = f"{item.feature} {item.reason}".lower()
        severity = "ERROR" if "clock" in lowered or "cdc" in lowered else "WARNING"
        add(
            "UNSUPPORTED_TEMPORAL_FEATURE",
            severity,
            f"{item.feature}: {item.reason}",
        )
    for item in temporal_facts.ambiguities:
        add("UNRESOLVED_TEMPORAL_AMBIGUITY", "WARNING", item.statement)

    event_ids = {item.id for item in temporal_facts.events}
    phase_ids = {item.id for item in temporal_facts.phases}
    temporal_ids = {
        *(item.id for item in temporal_facts.events),
        *(item.id for item in temporal_facts.phases),
        *(item.id for item in temporal_facts.latency_constraints),
        *(item.id for item in temporal_facts.relations),
        *(item.id for item in temporal_facts.invariants),
        *(item.id for item in temporal_facts.ambiguities),
        *(item.id for item in temporal_facts.unsupported_features),
    }
    logical_objects = {
        *(item.object for item in temporal_facts.logical_value_sequences),
        *(item.logical_object for item in temporal_facts.invariants if item.logical_object),
        *architecture.architecture_logical_objects,
    }
    logical_tags = {tag for item in temporal_facts.logical_value_sequences for tag in item.tags}

    owners: dict[str, list[str]] = {}
    for assignment in architecture.module_assignments:
        if assignment.module not in expected_modules:
            add(
                "UNKNOWN_ASSIGNMENT_MODULE",
                "ERROR",
                f"Temporal assignment references unknown module `{assignment.module}`.",
                module=assignment.module,
            )
        for logical_state in assignment.owns_logical_state:
            owners.setdefault(logical_state, []).append(assignment.module)
            if logical_state not in logical_objects:
                add(
                    "UNKNOWN_LOGICAL_OBJECT",
                    "ERROR",
                    f"State ownership references unknown logical object `{logical_state}`.",
                    module=assignment.module,
                )
        for event_id in assignment.handles_event_ids:
            if event_id not in event_ids:
                add(
                    "UNKNOWN_EVENT_REFERENCE",
                    "ERROR",
                    f"Assignment references unknown event `{event_id}`.",
                    module=assignment.module,
                )
        for phase_id in assignment.handles_phase_ids:
            if phase_id not in phase_ids:
                add(
                    "UNKNOWN_PHASE_REFERENCE",
                    "ERROR",
                    f"Assignment references unknown phase `{phase_id}`.",
                    module=assignment.module,
                )
    for logical_state, modules in owners.items():
        if len(modules) > 1:
            add(
                "DUPLICATE_STATE_OWNER",
                "ERROR",
                f"Logical state `{logical_state}` has multiple owners: {modules}.",
            )

    obligation_by_id = {item.id: item for item in architecture.module_obligations}
    all_bound_obligations: dict[str, list[tuple[str, str]]] = {}

    for module in expected_modules:
        skeleton = skeletons.get(module)
        binding = bindings.get(module)
        if skeleton is None:
            add("MISSING_MODULE_SKELETON", "ERROR", "Module skeleton export is missing.", module=module)
            continue
        if binding is None:
            add("MISSING_MODULE_TIMING_BINDING", "ERROR", "Module timing binding is missing.", module=module)
            continue

        block_kind_by_id = {item.block_id: item.block_kind for item in skeleton.structural_blocks}
        signal_names = {item.physical_signal for item in binding.signal_bindings}
        reported_local_objects: set[str] = set()
        for signal in binding.signal_bindings:
            if signal.logical_object not in logical_objects:
                if signal.logical_object not in reported_local_objects:
                    add(
                        "LOCAL_LOGICAL_OBJECT_REFINEMENT",
                        "WARNING",
                        f"Stage3 introduces local refinement object `{signal.logical_object}` "
                        "that is not enumerated by Stage1T.",
                        module=module,
                        block_id=signal.owner_block_id,
                    )
                    reported_local_objects.add(signal.logical_object)
            if signal.owner_block_id and signal.owner_block_id not in block_kind_by_id:
                add(
                    "UNKNOWN_BLOCK_REFERENCE",
                    "ERROR",
                    f"Signal `{signal.physical_signal}` references unknown owner block `{signal.owner_block_id}`.",
                    module=module,
                    block_id=signal.owner_block_id,
                )
            unknown_tags = [tag for tag in signal.logical_value_tags if tag not in logical_tags]
            if unknown_tags:
                add(
                    "UNKNOWN_LOGICAL_VALUE_TAG",
                    "ERROR",
                    f"Signal `{signal.physical_signal}` references unknown tags {unknown_tags}.",
                    module=module,
                    block_id=signal.owner_block_id,
                )
            if any("[" in tag or "]" in tag or "*" in tag for tag in signal.logical_value_tags):
                add(
                    "UNVERIFIED_LOGICAL_TAG_PATTERN",
                    "WARNING",
                    f"Signal `{signal.physical_signal}` uses a tag pattern that v1 does not solve.",
                    module=module,
                    block_id=signal.owner_block_id,
                )

        for block_binding in binding.block_obligations:
            all_bound_obligations.setdefault(block_binding.obligation_id, []).append(
                (module, block_binding.block_id)
            )
            obligation = obligation_by_id.get(block_binding.obligation_id)
            if obligation is None:
                add(
                    "UNKNOWN_OBLIGATION_REFERENCE",
                    "ERROR",
                    f"Binding references unknown obligation `{block_binding.obligation_id}`.",
                    module=module,
                    block_id=block_binding.block_id,
                    obligation_id=block_binding.obligation_id,
                )
                continue
            if obligation.module != module:
                add(
                    "OBLIGATION_MODULE_MISMATCH",
                    "ERROR",
                    f"Obligation belongs to `{obligation.module}`, not `{module}`.",
                    module=module,
                    block_id=block_binding.block_id,
                    obligation_id=block_binding.obligation_id,
                )
            block_kind = block_kind_by_id.get(block_binding.block_id)
            if block_kind is None:
                add(
                    "UNKNOWN_BLOCK_REFERENCE",
                    "ERROR",
                    f"Obligation references unknown block `{block_binding.block_id}`.",
                    module=module,
                    block_id=block_binding.block_id,
                    obligation_id=block_binding.obligation_id,
                )
            if (
                any(access.at == "POST_EDGE" for access in block_binding.writes)
                and block_kind != "seq"
            ):
                add(
                    "POST_EDGE_WRITE_REQUIRES_SEQ_BLOCK",
                    "ERROR",
                    "An obligation with a POST_EDGE write must bind to a seq block.",
                    module=module,
                    block_id=block_binding.block_id,
                    obligation_id=block_binding.obligation_id,
                )
            if obligation.guard or block_binding.guard:
                add(
                    "UNRESOLVED_GUARD",
                    "WARNING",
                    "The obligation contains a guard string that v1 records but does not solve.",
                    module=module,
                    block_id=block_binding.block_id,
                    obligation_id=block_binding.obligation_id,
                )
            _compare_accesses(
                expected=obligation.reads,
                actual=block_binding.reads,
                label="reads",
                add=add,
                module=module,
                block_id=block_binding.block_id,
                obligation_id=block_binding.obligation_id,
            )
            _compare_accesses(
                expected=obligation.writes,
                actual=block_binding.writes,
                label="writes",
                add=add,
                module=module,
                block_id=block_binding.block_id,
                obligation_id=block_binding.obligation_id,
            )
            _compare_accesses(
                expected=obligation.combinational_outputs,
                actual=block_binding.combinational_outputs,
                label="combinational_outputs",
                add=add,
                module=module,
                block_id=block_binding.block_id,
                obligation_id=block_binding.obligation_id,
            )
            for access in [
                *block_binding.reads,
                *block_binding.writes,
                *block_binding.combinational_outputs,
            ]:
                if access.logical_object not in logical_objects:
                    if access.logical_object not in reported_local_objects:
                        add(
                            "LOCAL_LOGICAL_OBJECT_REFINEMENT",
                            "WARNING",
                            f"Stage3 introduces local refinement object `{access.logical_object}` "
                            "that is not enumerated by Stage1T.",
                            module=module,
                            block_id=block_binding.block_id,
                            obligation_id=block_binding.obligation_id,
                        )
                        reported_local_objects.add(access.logical_object)
                if access.logical_value_tag and access.logical_value_tag not in logical_tags:
                    add(
                        "UNKNOWN_LOGICAL_VALUE_TAG",
                        "ERROR",
                        f"Access references unknown tag `{access.logical_value_tag}`.",
                        module=module,
                        block_id=block_binding.block_id,
                        obligation_id=block_binding.obligation_id,
                    )
                if access.signal not in signal_names:
                    add(
                        "UNBOUND_PHYSICAL_SIGNAL",
                        "ERROR",
                        f"Access references signal `{access.signal}` without a signal binding.",
                        module=module,
                        block_id=block_binding.block_id,
                        obligation_id=block_binding.obligation_id,
                    )

    for obligation in architecture.module_obligations:
        if obligation.event_id and obligation.event_id not in event_ids:
            add(
                "UNKNOWN_EVENT_REFERENCE",
                "ERROR",
                f"Obligation references unknown event `{obligation.event_id}`.",
                module=obligation.module,
                obligation_id=obligation.id,
            )
        if obligation.phase_id and obligation.phase_id not in phase_ids:
            add(
                "UNKNOWN_PHASE_REFERENCE",
                "ERROR",
                f"Obligation references unknown phase `{obligation.phase_id}`.",
                module=obligation.module,
                obligation_id=obligation.id,
            )
        unknown_sources = [item for item in obligation.source_temporal_ids if item not in temporal_ids]
        if unknown_sources:
            add(
                "UNKNOWN_TEMPORAL_SOURCE",
                "ERROR",
                f"Obligation references unknown temporal source IDs {unknown_sources}.",
                module=obligation.module,
                obligation_id=obligation.id,
            )
        for access in [*obligation.reads, *obligation.writes, *obligation.combinational_outputs]:
            if access.logical_object not in logical_objects:
                add(
                    "UNKNOWN_LOGICAL_OBJECT",
                    "ERROR",
                    f"Obligation access references unknown object `{access.logical_object}`.",
                    module=obligation.module,
                    obligation_id=obligation.id,
                )
            if access.logical_value_tag and access.logical_value_tag not in logical_tags:
                add(
                    "UNKNOWN_LOGICAL_VALUE_TAG",
                    "ERROR",
                    f"Obligation access references unknown tag `{access.logical_value_tag}`.",
                    module=obligation.module,
                    obligation_id=obligation.id,
                )
        locations = all_bound_obligations.get(obligation.id, [])
        if not locations:
            add(
                "MISSING_OBLIGATION_BINDING",
                "ERROR",
                "Architecture obligation has no block binding.",
                module=obligation.module,
                obligation_id=obligation.id,
            )
        elif len(locations) > 1:
            add(
                "DUPLICATE_OBLIGATION_BINDING",
                "ERROR",
                f"Architecture obligation is bound multiple times: {locations}.",
                module=obligation.module,
                obligation_id=obligation.id,
            )

    known_transfer_ids = {item.id for item in architecture.cross_module_transfers}
    transfer_endpoint_map: dict[str, dict[str, list[tuple[str, str]]]] = {}
    for module, binding in bindings.items():
        signal_names = {item.physical_signal for item in binding.signal_bindings}
        for endpoint in binding.transfer_bindings:
            if endpoint.transfer_id not in known_transfer_ids:
                add(
                    "UNKNOWN_TRANSFER_REFERENCE",
                    "ERROR",
                    f"Binding references unknown transfer `{endpoint.transfer_id}`.",
                    module=module,
                    block_id=endpoint.block_id,
                )
            if endpoint.physical_signal not in signal_names:
                add(
                    "UNBOUND_TRANSFER_SIGNAL",
                    "ERROR",
                    f"Transfer endpoint signal `{endpoint.physical_signal}` has no signal binding.",
                    module=module,
                    block_id=endpoint.block_id,
                )
            transfer_endpoint_map.setdefault(endpoint.transfer_id, {}).setdefault(
                endpoint.endpoint,
                [],
            ).append(
                (
                    module,
                    endpoint.physical_signal,
                )
            )
    for transfer in architecture.cross_module_transfers:
        endpoints = transfer_endpoint_map.get(transfer.id, {})
        producer_entries = endpoints.get("producer", [])
        consumer_entries = endpoints.get("consumer", [])
        if len(producer_entries) != 1 or len(consumer_entries) != 1:
            add(
                "INCOMPLETE_TRANSFER_BINDING",
                "ERROR",
                "Transfer requires exactly one producer and one consumer binding; "
                f"found producer={producer_entries}, consumer={consumer_entries}.",
                obligation_id=transfer.id,
            )
        else:
            producer = producer_entries[0]
            consumer = consumer_entries[0]
            if producer[0] != transfer.producer or consumer[0] != transfer.consumer:
                add(
                    "TRANSFER_ENDPOINT_MODULE_MISMATCH",
                    "ERROR",
                    f"Transfer endpoints do not match {transfer.producer}->{transfer.consumer}.",
                    obligation_id=transfer.id,
                )
        if transfer.logical_object not in logical_objects:
            add(
                "UNKNOWN_LOGICAL_OBJECT",
                "ERROR",
                f"Transfer references unknown object `{transfer.logical_object}`.",
                obligation_id=transfer.id,
            )
        unknown_transfer_sources = [
            item for item in transfer.source_temporal_ids if item not in temporal_ids
        ]
        if unknown_transfer_sources:
            add(
                "UNKNOWN_TEMPORAL_SOURCE",
                "ERROR",
                f"Transfer references unknown temporal source IDs {unknown_transfer_sources}.",
                obligation_id=transfer.id,
            )
        if (
            transfer.delivery == "REGISTERED"
            and transfer.visible_at == "POST_EDGE"
            and transfer.sampled_at == "PRE_EDGE"
            and transfer.required_cycle_offset == 0
        ):
            add(
                "REGISTERED_VALUE_NOT_VISIBLE_AT_SAME_EDGE",
                "ERROR",
                "A POST_EDGE registered value cannot be consumed at PRE_EDGE of the same edge.",
                obligation_id=transfer.id,
            )

    if bindings:
        add(
            "PLANNED_SIGNAL_NAMES_REQUIRE_CODEGEN_CHECK",
            "WARNING",
            "Physical signal names are planning bindings and must be checked against Stage5 output.",
        )

    status = (
        "fail"
        if any(item.severity == "ERROR" for item in issues)
        else "warning"
        if issues
        else "pass"
    )
    return TimingBindingCheckArtifact(
        task_id=task_id,
        input_fingerprint=input_fingerprint,
        status=status,
        issues=issues,
    )


def _compare_accesses(
    *,
    expected: Iterable,
    actual: Iterable,
    label: str,
    add,
    module: str,
    block_id: str,
    obligation_id: str,
) -> None:
    expected_keys = [
        (item.logical_object, item.logical_value_tag, item.at)
        for item in expected
    ]
    actual_keys = [
        (item.logical_object, item.logical_value_tag, item.at)
        for item in actual
    ]
    expected_counts = Counter(expected_keys)
    actual_counts = Counter(actual_keys)
    missing = list((expected_counts - actual_counts).elements())
    if missing:
        add(
            "MISSING_ARCHITECTURE_ACCESS",
            "ERROR",
            f"{label} must preserve Stage2.5 accesses; missing {missing}. "
            f"Stage3 accesses are {actual_keys}. Additional Stage3 refinement accesses are allowed.",
            module=module,
            block_id=block_id,
            obligation_id=obligation_id,
        )
