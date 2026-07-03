"""Formateadores de números."""


def format_int(value: float | int) -> str:
    """Formato entero con separador de miles."""
    try:
        return f"{int(value):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "0"


def format_percent(value: float, decimals: int = 1) -> str:
    """Formato porcentaje (recibe 0.042 -> '4.2%')."""
    try:
        return f"{value * 100:.{decimals}f}%"
    except (ValueError, TypeError):
        return "0.0%"


def format_percent_raw(value: float, decimals: int = 1) -> str:
    """Formato porcentaje para valores YA expresados en puntos (recibe 4.2 -> '4.2%').

    Usar con KPIs cuya fórmula ya multiplica por 100 (eficiencia_pauta,
    eficiencia_bruta, eficiencia_global) para no re-escalar por 100 dos veces.
    """
    try:
        return f"{value:.{decimals}f}%"
    except (ValueError, TypeError):
        return "0.0%"


def format_delta(value: float, is_percent: bool = False) -> str:
    """Formato de delta para deltas positivos/negativos (+23, -5, +1.2 pts, etc.)."""
    if is_percent:
        return f"{value * 100:+.1f} pts"
    return f"{value:+,.0f}".replace(",", ".")
