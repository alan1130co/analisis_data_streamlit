from functools import lru_cache
from pathlib import Path
import streamlit as st

_STYLES_DIR = Path(__file__).parent
_LOAD_ORDER = ["theme.css", "base.css", "kpi_cards.css", "responsive.css", "breakdowns.css"]


@lru_cache(maxsize=1)
def _load_all_css() -> str:
    parts = []
    for name in _LOAD_ORDER:
        path = _STYLES_DIR / name
        if path.exists():
            parts.append(f"/* === {name} === */\n{path.read_text(encoding='utf-8')}")
    return "\n\n".join(parts)


def inject_custom_css() -> None:
    st.markdown(f"<style>{_load_all_css()}</style>", unsafe_allow_html=True)
