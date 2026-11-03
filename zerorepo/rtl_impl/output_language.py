"""Optional run-local language requirement; legacy callers keep their dialect."""
from contextlib import contextmanager
from contextvars import ContextVar

_language=ContextVar('rtl_output_language',default=None)
_interactive_limit=ContextVar('rtl_interactive_module_limit',default=None)
VERILOG_REQUIREMENT='DUT implementation MUST use synthesizable IEEE Verilog-2001, .v files, wire/reg and always @ syntax. Do not use SystemVerilog logic, always_ff, always_comb, interfaces, packages or unpacked array ports in DUT. Verification testbench may use SystemVerilog. Preserve the exact confirmed top and interface. This overrides generic SystemVerilog examples in other instructions.'

def requirement():
    parts=[VERILOG_REQUIREMENT] if _language.get()=='verilog' else []
    limit=_interactive_limit.get()
    if limit is not None:
        parts.append(f'Interactive workbench planning profile: at most {limit} design modules. Use the smallest correct decomposition; avoid unnecessary wrapper/helper modules. Prefer at most 3 substantial behavioral blocks and 3 code-generation subtasks per module, combining closely related logic. Keep skeleton documents, contracts and plans concise, reference original specification IDs instead of repeating paragraphs, and avoid expanding illustrative examples. Original requirements, timing, interfaces and acceptance criteria remain authoritative; never truncate required behavior to meet these preferences. The original CLI planning profile is unchanged.')
    return '\n\n'.join(parts)

def current_language():return _language.get()

@contextmanager
def interactive_planning(max_modules):
    token=_interactive_limit.set(max_modules)
    try:yield
    finally:_interactive_limit.reset(token)

@contextmanager
def output_language(value):
    token=_language.set(value)
    try:yield
    finally:_language.reset(token)
