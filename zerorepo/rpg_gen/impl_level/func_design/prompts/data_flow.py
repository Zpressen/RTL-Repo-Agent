COMPONENT_DATA_FLOW = """
You are a system architect designing the **file-level and module-level data flow** for an RTL repository.

Your goal is to describe **how signals, configuration, shared definitions, verification stimuli, and build artifacts move** between RTL files as a **directed acyclic graph (DAG)** of edges.
Each edge represents one meaningful handoff between distinct RTL/build files.

## Hard Constraint: The Graph MUST Be Acyclic
- The final data flow **must be a strict DAG**:  
  There must be **no path** that starts from a subtree and eventually returns to the **same** subtree via one or more edges.
- In particular, you **must not** create:
  - Direct 2-node cycles, e.g. `A → B` and `B → A`
  - Longer cycles, e.g. `A → B → C → A`
  - Any chain that, when followed, returns to an earlier subtree.
- If the natural design seems to require feedback or iteration, you **must instead**:
  - Introduce explicit, one-directional stages (e.g. `Trainer → MetricsCollector → Reporting`), or
  - Model the feedback as a new, downstream component instead of sending data “backwards”.
- Before calling any tool, mentally verify that your proposed `data_flow` is a DAG with **no cycles of any length**.

## Data Flow Guidelines
- Treat each edge as a meaningful handoff between two **distinct** RTL/build files (no self-loops like `A → A`).
- The overall graph must be **connected enough** that:
  - Every target RTL file defined in the task appears **at least once** as a producer or consumer.
- Prefer RTL-native handoff categories such as:
  - shared package definitions,
  - CSR/configuration state,
  - FIFO payload/data paths,
  - status/interrupt signaling,
  - module instance connectivity,
  - testbench stimuli/checker observations,
  - build/lint/simulation artifact flow.
- Reuse logical data types across edges when they represent the same structure, instead of inventing many ad-hoc labels.
- Ensure naming is consistent and domain-aware so the flow is understandable as an RTL architecture diagram.

## RTL Knowledge Graph Usage
- A read-only RTL KG query tool may be available in this task.
- The repository KG is written by the pipeline after skeleton/graph/code stages; you only query it.
- Before inventing file/module dependencies, instance relationships, or signal connectivity, prefer querying the RTL KG.
- Write only read-only Cypher. Do not attempt to modify the graph.
- Query using RTL-native entities and relations such as `Module`, `Instance`, `Port`, `Signal`, `Param`, `Package`, `OF_MODULE`, `CONNECTS`, `DRIVES`, `IMPORTS`, and `INCLUDES`.
- Use KG facts to confirm repository structure first, then synthesize the final file-level data flow DAG.

## Action Space
{Tool_Description}

## Output Format
Your response must contain exactly one <think> block and exactly one <tool_call> block, with no other content outside these two blocks:

<think>
Your internal reasoning and drafts—treat this like architectural scratch work.
Carefully design a **cycle-free** (DAG) data flow:  
- Enumerate the RTL files and their responsibilities.
- Propose candidate edges and check whether they introduce any cycles.
- If you detect a potential cycle, refactor the design (e.g., by inserting intermediate stages or changing responsibilities) until the graph is acyclic.
Only once you are confident the graph is a DAG, prepare the final tool call.
</think>
<tool_call>
{
  "tool_name": "...",
  "parameters": {...}
}
</tool_call>
""".strip()


COMPONENT_DATA_FLOW_REVIEW = """
You are reviewing the RTL file-level data architecture of the repository.

The submitted data flow graph defines how RTL/build files collaborate, what handoff contracts they expose, and how responsibilities are split.
If this graph is incorrect, vague, or overcomplicated, the entire system will suffer from tight coupling and unclear interfaces.

Review this as a strategic decision about how information moves across architectural boundaries.

## Constraints
- Every target RTL file must appear at least once as a producer ("source") or consumer ("target").
- The graph must be a Directed Acyclic Graph (no cycles, no self-loops).
- Data edges should be semantically plausible for RTL/build design (realistic producer -> consumer relationships).
- Prefer clear, reusable RTL/build handoff types over ad-hoc labels.

## Review Dimensions
1. Data Integrity
   - Are data types and contracts consistent and believable across edges?
   - Are there obvious type mismatches or broken assumptions between producer and consumer?
2. Flow Logic
   - Do the directions of edges make sense given each subtree’s role?
   - Is the graph acyclic and free of self-loops and obviously redundant or unjustified flows?
3. Transformation Clarity
   - Is it clear what happens to data at each hop (transformation field)?
   - Do transformations align with the roles of the involved subtrees, or are they vague/hand-wavy?
4. Coverage
   - Are all RTL files from {trees_names} represented, with no missing or extraneous names?
   - Are there isolated or under-connected files that indicate gaps or unclear responsibilities?

## Output Format
Return **only** a valid JSON object in the following format:
{
  "review": {
    "Data Integrity": {
      "feedback": "<Your feedback here>",
      "pass": true/false
    },
    "Flow Logic": {
      "feedback": "<Your feedback here>",
      "pass": true/false
    },
    "Transformation Clarity": {
      "feedback": "<Your feedback here>",
      "pass": true/false
    },
    "Coverage": {
      "feedback": "<Your feedback here>",
      "pass": true/false
    }
  },
  "final_pass": true/false
}

Rules:
- `final_pass` should be `true` only if all four dimensions pass, or if remaining issues are minor and easily fixable.
- All `feedback` fields must provide concrete, actionable guidance.
- Do not add new fields or categories beyond the four listed.
""".strip()


GENERATE_DATA_FLOW_TOOL = """
## Tool Name: generate_data_flow

### Description
Generate and validate a **data flow graph** between RTL/build files, ensuring:
- All edges are well-formed.
- All referenced files are valid.
- Every required RTL/build file participates in the flow.
- **The overall graph is a Directed Acyclic Graph (DAG)** — i.e., there are **no cycles** of any length.

### When to Use
Use this tool whenever defining or updating RTL file-level data flow (who hands what to whom) and you need to check that:

- All referenced RTL/build files exist in the implementation architecture.
- No required RTL/build file is completely unused.
- Each flow unit contains complete and meaningful information.
- Transformations are non-empty and clearly described.
- **All `source -> target` edges together form an acyclic graph** (no feedback loops).

If the natural design seems to require feedback or iteration, you must restructure it into one-directional stages so that the resulting graph remains a DAG.

### Parameters (JSON Schema)

{
  "tool_name": "generate_data_flow",
  "parameters": {
    "data_flow": [
      {
        "source": "source_file_path",
        "target": "target_file_path",
        "data_id": "unique name or description of the RTL/build handoff",
        "data_type": "logical type or structure of the handoff (e.g., 'RTLPackage', 'ModulePorts', 'CSRConfig', 'SimulationArtifact')",
        "transformation": "1–2 sentences describing how the data is processed / validated / serialized / enriched during this transfer"
      }
    ]
  }
}

#### Field Summary
- **data_flow** (list of objects)  
  Non-empty list of directed edges in the data flow graph that together must form a DAG (no cycles).
- **source** (string)  
  Path or name of the RTL/build file that produces this handoff; must be a valid target file and different from `target`.
- **target** (string)  
  Path or name of the RTL/build file that consumes this handoff; must be a valid target file and different from `source`.
- **data_id** (string)  
  Human-readable identifier for this specific RTL/build exchange (e.g., `"uart_pkg_exports"`, `"rx_fifo_write_data"`, `"sim_waveforms"`).
- **data_type** (string)  
  Logical type or schema of the handoff being transferred (e.g., `"RTLPackage"`, `"ModulePorts"`, `"SimulationArtifact"`).
- **transformation** (string)  
  One–two sentences describing what happens to the data on this edge, and it must not be empty or `"none"`.

### Graph Constraints
- For all (`source`, `target`) edges:
  - No self-loops: `source != target`.
  - No cycles of any length:
    - No 2-node cycle: `A -> B` **and** `B -> A`.
    - No longer cycle: `A -> B -> C -> ... -> A`.
- Every required subtree should appear at least once as a producer or consumer.
- Every required RTL/build file should appear at least once as a producer or consumer.

### Example Tool Call
{
  "tool_name": "generate_data_flow",
  "parameters": {
    "data_flow": [
      {
        "source": "rtl/pkg/uart_pkg.sv",
        "target": "rtl/modules/uart_rx.sv",
        "data_id": "uart_pkg_exports",
        "data_type": "RTLPackage",
        "transformation": "Shared typedefs, constants, and configuration fields are imported into uart_rx so the module compiles against the canonical UART package contract."
      },
      {
        "source": "rtl/modules/uart_rx.sv",
        "target": "rtl/axi_uart_top.sv",
        "data_id": "rx_parallel_data_and_status",
        "data_type": "ModulePorts",
        "transformation": "The receiver exposes decoded byte data, status flags, and FIFO write-side signals for top-level integration."
      },
      {
        "source": "rtl/axi_uart_top.sv",
        "target": "tb/axi_uart_tb.sv",
        "data_id": "dut_external_interface",
        "data_type": "TopLevelPorts",
        "transformation": "The testbench drives and observes the canonical top-level DUT ports to validate integrated UART behavior."
      }
    ]
  }
}
""".strip()
