"""
RTL implementation package.

Exports are resolved lazily to avoid importing the full Phase 1 / LLM stack when
only lightweight bridge utilities are needed.
"""

from typing import TYPE_CHECKING

__all__ = ["SpecFactsParser", "SpecFacts", "RTLImplBuilder", "RTLPropLevelAdapter"]


if TYPE_CHECKING:
    from .phase1_spec_parsing import SpecFactsParser, SpecFacts
    from .prop_level_adapter import RTLPropLevelAdapter
    from .rtl_impl_builder import RTLImplBuilder


def __getattr__(name: str):
    if name in {"SpecFactsParser", "SpecFacts"}:
        from .phase1_spec_parsing import SpecFactsParser, SpecFacts

        exports = {
            "SpecFactsParser": SpecFactsParser,
            "SpecFacts": SpecFacts,
        }
        return exports[name]

    if name == "RTLImplBuilder":
        from .rtl_impl_builder import RTLImplBuilder

        return RTLImplBuilder

    if name == "RTLPropLevelAdapter":
        from .prop_level_adapter import RTLPropLevelAdapter

        return RTLPropLevelAdapter

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
