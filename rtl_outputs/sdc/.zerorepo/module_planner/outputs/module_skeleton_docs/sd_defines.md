# MODULE_SKELETON_DOC v1

## 0. Module Identity
- module_name: sd_defines
- file_path: rtl/sd_defines.v
- source_refs:
  - module_contract_ref: none (definition-only module)
  - repo_skeleton_ref: repo_skeleton_v1::sd_defines
  - spec_ref: sd_defines.md
- planning_note: This module provides a single, flat group of preprocessor defines and parameters. No instantiable hardware is intended. All configuration options from the spec table are captured as `define` statements; mutually exclusive groups require a build-time selection.

## 1. Module Frame
```verilog
// SD controller global defines
// <block: decl_macros_and_defines>
```

## 2. Structural Skeleton
### Block
- block_id: B1
- block_label: decl_macros_and_defines
- block_kind: decl
- required: true
- purpose: Declare all SD‑controller configuration macros (`define`s) listed in the specification.
- code_shape: preprocessor definition group
- depends_on: []
- placeholder:
```verilog
// skeleton only: preprocessor definition cluster
// all spec‑listed define options with their allowed values / mutual exclusivity
// comments differentiate compile‑time choices (BIG_ENDIAN vs LITTLE_ENDIAN, etc.)
```
- must_appear:
  - Definitions for every entry in the spec table (BIG_ENDIAN, LITTLE_ENDIAN, SIM, SYN, SDC_IRQ_ENABLE, ACTEL, BD_WIDTH, BD_SIZE, RAM_MEM_WIDTH_16, RAM_MEM_WIDTH, RESEND_MAX_CNT, MEM_OFFSET, RESET_CLK_DIV, SD_CLK_BUS_CLK, SD_CLK_SEP, SD_CLK_STATIC, SD_CLK_DYNAMIC, BLOCK_SIZE, SD_BUS_WIDTH_4, SD_BUS_W, FIFO_RX_MEM_DEPTH, FIFO_RX_MEM_ADR_SIZE, FIFO_TX_MEM_DEPTH, FIFO_TX_MEM_ADR_SIZE).
  - Clear comment guidance for exclusive options (e.g., only one of BIG_ENDIAN/LITTLE_ENDIAN, SIM/SYN, SD_CLK_* group).
- may_appear:
  - Internal helper defines strictly derived from the above (e.g., log2 derivations, one‑hot selector for exclusive groups).
- retrieval_focus:
  - values of BD_SIZE, FIFO depths, clock mode, endianness (compile‑time constants used by all other SD modules)

## 3. Behavioral Overlay
### Module-Level Behavioral Summary
- control_style: undecided
- semantic_modes:
  - BUILD_TIME_CONFIG: A single set of active defines is selected before synthesis/simulation; no run‑time mode switching.
- state_model: none (no registered objects, no runtime state)
- global_invariants:
  - All non‑selected mutually exclusive options must be left undefined or explicitly deactivated according to the spec.
  - Output is a fixed set of global macros visible to all later-compiled modules.
- open_semantic_questions:
  - Whether default values exist for optional defines (e.g., SDC_IRQ_ENABLE absent) is unspecified; the skeleton must allow optional presence.

### Block Behavioral Overlay
- block_id: B1
- responsibilities:
  - Provide every configuration macro needed by other SD controller modules.
  - Document the valid domain and mutual exclusion rules for each group.
- timing_semantics: none (compile‑time static)
- touched_objects: none (no hardware objects, only textual substitution tokens)
- coupling_rules:
  - Other modules `include` this file and rely on the macro names exactly as defined.
  - Changes to macro names or value domains require synchronized updates across all dependent modules.
- forbidden_drift:
  - Do not instantiate hardware (no `reg`, `wire`, `module`, or sequential logic).
  - Do not add run‑time configuration registers or dynamic redefinition logic not mentioned in the spec.

## 4. Decision Ledger
### Chosen Decision
- topic: structural granularity
- decision: All defines reside in a single declaration block; no sub‑blocking is required because there is no control flow or data dependency among them.
- reason: The module is a flat set of compile‑time constants; splitting would add artificial hierarchy not present in the spec.

### Deferred Decision
- items:
  - Exact mapping of decimal/hex values for derived parameters (e.g., log2‑based ADR_SIZE) is deferred to code generation.
  - Which mutually exclusive group member becomes the “active” definition is a build‑system choice, not a skeleton choice.

### Structural Risk
- items:
  - If the file grows with additional non‑standard defines not in the spec, auto‑retrieval may mix project‑specific additions with spec‑driven definitions.

### Behavioral Risk
- items:
  - Omitting a required define or mismatching a mutually exclusive group may cause downstream modules to mis‑interpret bus widths, clock sources, or buffer sizes; the skeleton cannot validate compile‑time completeness.