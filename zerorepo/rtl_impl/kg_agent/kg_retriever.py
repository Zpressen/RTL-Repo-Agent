from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from . import kg_query_templates as templates


class KGRetriever:
    """Fixed-template RTL KG retrieval helper."""

    _SIGNAL_PATTERNS = [
        re.compile(r"\bsignal\s+([A-Za-z_][A-Za-z0-9_$]*)\b", re.IGNORECASE),
        re.compile(r"\b(?:fail|failed|mismatch|mismatched)\b[^\n:]*[:=]\s*([A-Za-z_][A-Za-z0-9_$]*)", re.IGNORECASE),
        re.compile(r"\b([A-Za-z_][A-Za-z0-9_$]*)_(?:dut|ref)\b", re.IGNORECASE),
    ]

    def __init__(self, kg_service: Any):
        self.kg_service = kg_service

    def get_child_module_context(self, parent_module: str) -> Dict[str, Any]:
        return self.kg_service.query(
            templates.GET_CHILD_MODULE_CONTEXT,
            {"parent_module": parent_module},
            limit=100,
        )

    def get_module_interface(self, module_name: str) -> Dict[str, Any]:
        result = self.kg_service.query(
            templates.GET_MODULE_INTERFACE,
            {"module_name": module_name},
            limit=25,
        )
        return self._normalize_module_interface_result(module_name, result)

    def get_instance_context(
        self,
        parent_module: str,
        child_module: str | None = None,
        instance_name: str | None = None,
    ) -> Dict[str, Any]:
        return self.kg_service.query(
            templates.GET_INSTANCE_CONTEXT,
            {
                "parent_module": parent_module,
                "child_module": child_module or "",
                "instance_name": instance_name or "",
            },
            limit=100,
        )

    def get_signal_debug_context(self, module_name: str, signal_name: str) -> Dict[str, Any]:
        return self.kg_service.query(
            templates.GET_SIGNAL_DEBUG_CONTEXT,
            {"module_name": module_name, "signal_name": signal_name},
            limit=100,
        )

    def get_failure_context(self, error_log: str, current_module: str) -> Dict[str, Any]:
        signal_names = self._extract_signal_names(error_log)
        status = self.kg_service.query(
            templates.GET_FAILURE_MODULE_STATUS,
            {"module_name": current_module},
            limit=10,
        )
        signals = [
            {
                "signal": signal,
                "context": self.get_signal_debug_context(current_module, signal),
            }
            for signal in signal_names
        ]
        return {
            "module": current_module,
            "signals": signal_names,
            "module_status": status,
            "signal_contexts": signals,
            "child_module_context": self.get_child_module_context(current_module),
        }

    def _extract_signal_names(self, error_log: str) -> List[str]:
        found: List[str] = []
        for pattern in self._SIGNAL_PATTERNS:
            for match in pattern.finditer(error_log or ""):
                name = match.group(1)
                if name not in found:
                    found.append(name)
        return found[:8]

    def _normalize_module_interface_result(self, module_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
        rows = result.get("rows", []) if isinstance(result, dict) else []
        row = rows[0] if rows else {}
        simulation_passed = self._coerce_bool(row.get("simulation_passed")) if row else False
        return {
            "module": str(row.get("module") or module_name),
            "module_path": str(row.get("module_path") or ""),
            "module_start_line": row.get("module_start_line"),
            "module_end_line": row.get("module_end_line"),
            "file_path": str(row.get("final_rtl_path") or row.get("module_path") or ""),
            "final_rtl_path": str(row.get("final_rtl_path") or ""),
            "simulation_status": str(row.get("simulation_status") or ""),
            "simulation_passed": simulation_passed,
            "child_status": "verified" if simulation_passed else "candidate",
            "ports": self._normalize_symbols(row.get("ports", []), kind="port"),
            "parameters": self._normalize_symbols(row.get("parameters", []), kind="parameter"),
            "raw_query": result,
        }

    def _normalize_symbols(self, symbols: Any, *, kind: str) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        if not isinstance(symbols, list):
            return normalized
        for symbol in symbols:
            if not isinstance(symbol, dict):
                continue
            name = str(symbol.get("name") or "").strip()
            if not name:
                continue
            attrs = self._parse_attrs(symbol.get("attrs"))
            item = {
                "name": name,
                "path": str(symbol.get("path") or ""),
                "sl": symbol.get("sl"),
                "el": symbol.get("el"),
                "attrs": attrs,
            }
            if kind == "port":
                item.update(
                    {
                        "direction": str(attrs.get("dir") or attrs.get("direction") or ""),
                        "width": str(attrs.get("width_expr") or attrs.get("width") or ""),
                    }
                )
            else:
                item.update(
                    {
                        "value": str(attrs.get("value_short") or attrs.get("value") or ""),
                        "width": str(attrs.get("width_expr") or attrs.get("width") or ""),
                    }
                )
            normalized.append(item)
        return normalized

    def _parse_attrs(self, attrs: Any) -> Dict[str, Any]:
        if isinstance(attrs, dict):
            return attrs
        if isinstance(attrs, str) and attrs.strip():
            try:
                parsed = json.loads(attrs)
            except json.JSONDecodeError:
                return {"raw": attrs}
            return parsed if isinstance(parsed, dict) else {"raw": attrs}
        return {}

    def _coerce_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "pass", "passed"}
        return bool(value)
