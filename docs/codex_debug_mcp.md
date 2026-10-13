# Codex RTL Debug MCP

ZeroRepo can use Codex as the system-level RTL debugger while retaining the
existing planning/generation pipeline and objective verifier.

## Enable the backend

Configure the normal pipeline in `configs/zerorepo_config.yaml`:

```yaml
rtl_debug:
  backend: "codex"
  max_trials: 30
  codex_multi_agent: false
  codex_timeout: 10800
```

`ZEROREPO_CODEX_BIN` and `ZEROREPO_CODEX_MODEL` are optional. When the model is
unset, Codex uses its configured/default model. Authentication still comes from
the user's Codex installation; the spawned task ignores user Codex tool/plugin
configuration and receives only the run-scoped RTL Debug MCP server.

Readonly MCP calls are counted for experiment analysis but are not capped.
`ZEROREPO_CODEX_MULTI_AGENT` can enable Codex subagents for an explicit
experiment group; single-agent operation remains the default. The existing
`ZEROREPO_RTL_DEBUG_*` and `ZEROREPO_CODEX_*` environment variables remain
optional, higher-priority overrides for one-off experiments.

## Run layout and trust boundary

For each failing system simulation, `SystemDebugRunner` creates:

```text
debug_system/<top>/
├── codex_task/
│   ├── spec/       # initial specs, monitored as immutable
│   └── merged/     # the only accepted edit target (.v/.sv only)
└── codex_private/  # descriptor, baselines, candidates, KG config, logs
```

Codex starts with `codex_task/` as its workspace root under the Codex
`workspace-write` sandbox. The MCP server rejects symlinks, non-RTL files,
changed specs, stale candidates, and validation feedback that bypasses the
trial counter. The launcher also snapshots both visible trees before startup,
checks for out-of-scope files on exit, and restores a trusted baseline if the
MCP process exits dirty or cannot be reached.

The MCP server exposes exactly:

- `read_module_semantics`
- `query_rtl_kg`
- `trace_signal_cause`
- `list_vcd_signals`
- `probe_vcd`
- `run_check`
- `validate_rtl_changes`
- `get_debug_status`

Codex chooses the order in which it inspects the spec, RTL, KG, and waveform
evidence. The initial divergence is an advisory hint, not a required gate.
Codex edits RTL with its native file tools. A non-empty edit must go through
`validate_rtl_changes(action="evaluate")`, followed by an explicit `accept` or
`rollback`. Dynamic evidence is revision-tagged, and evidence becomes stale as
soon as the working RTL changes again.

## Completion semantics

The Codex final message never determines pass/fail. A normal turn that leaves a
failing accepted baseline is automatically resumed in the same persisted Codex
session until it passes, consumes the validation-trial budget, hits the global
timeout, or encounters a process/security failure. Each MCP stdio process
restores the accepted baseline, evidence, and cumulative counters from private
state. On process exit, unresolved dirty or pending changes are rolled back.
The parent process then runs the system verifier again against the accepted
`merged/` tree and only copies that tree back into the normal ZeroRepo workspace
when the transaction is clean.

The private directory records `debug_status.json`, validation journals, Codex
JSONL events, stderr, accepted/candidate snapshots, and the final verifier
output for experiment analysis.
