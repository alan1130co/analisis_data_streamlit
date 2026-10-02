"""Instrumentación temporal del flujo de sincronización con la API de
Clientify (ver auditoría de performance, octubre 2026).

Logger dedicado (no `print`) para que los tiempos por etapa queden en la
terminal donde corre `streamlit run`, con el formato `[SYNC] ...` pedido
para poder diagnosticar el cuello de botella real con logs reales en vez de
suposiciones. Pensado para removerse o bajarse a DEBUG una vez resuelto el
problema de performance que motivó esta instrumentación.
"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager

logger = logging.getLogger("sync")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


@contextmanager
def timed_stage(label: str):
    """Mide y loguea cuánto tarda el bloque `with` envuelto.

    Loguea un marcador de inicio (para poder ver en los logs si una etapa
    arrancó pero nunca terminó, p.ej. por una excepción) y al final el
    tiempo transcurrido, formato `[SYNC] Etapa <label>: X.XX segundos`.
    """
    start = time.perf_counter()
    logger.info("[SYNC] >>> Inicio: %s", label)
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        logger.info("[SYNC] Etapa %s: %.2f segundos", label, elapsed)


def log_stage(label: str, elapsed: float) -> None:
    """Loguea una etapa ya medida externamente (cuando no se puede usar un
    `with` porque el valor a medir no es un bloque de código contiguo, p.ej.
    diferenciar hit/miss de `st.cache_data`)."""
    logger.info("[SYNC] Etapa %s: %.2f segundos", label, elapsed)


def log_marker(message: str) -> None:
    """Loguea un mensaje suelto (sin medición), p.ej. para marcar hit/miss
    de cache o el inicio/fin de todo el flujo visible al usuario."""
    logger.info("[SYNC] %s", message)
