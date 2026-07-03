from datetime import date

from src.analytics.filters import (
    is_current_month,
    default_month_index,
    format_month_label,
)


def test_is_current_month_true_cuando_coincide_anio_y_mes():
    assert is_current_month(date(2026, 7, 1), today=date(2026, 7, 3))


def test_is_current_month_false_para_mes_anterior():
    assert not is_current_month(date(2026, 6, 1), today=date(2026, 7, 3))


def test_default_month_index_saltea_mes_en_curso():
    """Si hoy es 3 de julio y julio ya tiene leads (mes más reciente),
    el default debe ser junio (índice 1), no julio (índice 0)."""
    months = [date(2026, 7, 1), date(2026, 6, 1), date(2026, 5, 1)]
    assert default_month_index(months, today=date(2026, 7, 3)) == 1


def test_default_month_index_usa_mas_reciente_si_ya_esta_completo():
    """Si el mes más reciente con datos NO es el mes en curso (p.ej. ya
    pasó julio y estamos en agosto sin leads todavía), el default es 0."""
    months = [date(2026, 7, 1), date(2026, 6, 1)]
    assert default_month_index(months, today=date(2026, 8, 15)) == 0


def test_default_month_index_lista_vacia_no_crashea():
    assert default_month_index([], today=date(2026, 7, 3)) == 0


def test_default_month_index_un_solo_mes_en_curso_no_tiene_anterior():
    """Si el único mes disponible es el mes en curso, no hay a dónde
    saltar — se usa igual (índice 0)."""
    months = [date(2026, 7, 1)]
    assert default_month_index(months, today=date(2026, 7, 3)) == 0


def test_format_month_label_mes_en_curso_incluye_dias_transcurridos():
    mes = date(2026, 7, 1)
    label = format_month_label(mes, today=date(2026, 7, 3))
    base = mes.strftime("%B %Y").capitalize()
    assert label == f"{base} (en curso, 3 días)"


def test_format_month_label_mes_completo_sin_sufijo():
    mes = date(2026, 6, 1)
    label = format_month_label(mes, today=date(2026, 7, 3))
    assert label == mes.strftime("%B %Y").capitalize()
