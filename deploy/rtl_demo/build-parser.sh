#!/usr/bin/env bash
set -euo pipefail
# Usage: build-parser.sh AGENT_PYTHON REPO_ROOT CACHE_DIR
if [[ $# != 3 ]]; then echo 'Usage: build-parser.sh AGENT_PYTHON REPO_ROOT CACHE_DIR' >&2; exit 2; fi
export PYTHONPATH="$2"
export RTL_TS_CACHE_DIR="$3"
export RTL_TS_LANG_SO="$3/rtl_langs.so"
"$1" - <<'PY'
from zerorepo.rtl_impl.rtl_kg.rtl_file_graph_builder import VerilogTreeSitter
p=VerilogTreeSitter.get_parser()
tree=p.parse(b'module demo(input clk, output y); assign y=clk; endmodule')
if tree.root_node.has_error: raise SystemExit('Target Verilog parser failed')
print('Target parser build and AST check passed')
PY
