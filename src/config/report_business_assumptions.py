"""Supuestos de negocio que la IA necesita para analizar Segmentación Clave,
Embudo y Canales, y Gestión Comercial, pero que NO son 100% evidentes solo
leyendo el código/esquema de columnas — quedaron marcados "SUPUESTO: ..."
para que el usuario (negocio) los confirme o corrija.

Archivo separado y EDITABLE a propósito: para corregir un supuesto, editá
el texto de abajo — no hay que tocar `report_prompts.py` ni ninguna lógica.
Cada bloque se inyecta tal cual al final del contexto de negocio de su
sección (ver `src/config/report_prompts.py`).
"""
from __future__ import annotations

SUPUESTOS_SEGMENTACION = """
SUPUESTOS a confirmar con el negocio (si alguno es incorrecto, corregilo
en este archivo):
- SUPUESTO: no hay metas oficiales de distribución geográfica/demográfica
  (p.ej. "el 40% de los clientes debería ser de tal país") — evaluá
  concentración/diversificación solo en términos relativos (categoría
  líder vs. el resto), nunca contra una meta que no te fue dada.
- SUPUESTO: el género es una ESTIMACIÓN heurística a partir del primer
  nombre del cliente (no declarado por él) — siempre que lo menciones,
  aclaralo como aproximado.
""".strip()

SUPUESTOS_EMBUDO = """
SUPUESTOS a confirmar con el negocio (si alguno es incorrecto, corregilo
en este archivo):
- SUPUESTO: no hay una meta oficial de "% Eficiencia Real" o "% Efic.
  Bruta" por asesor — evaluá desempeño comparando asesores entre sí dentro
  del mismo payload, nunca contra un estándar externo.
- SUPUESTO: "Sin publicacion marcada"/"Sin canal (referido)" son categorías
  de dato faltante, no una categoría de negocio real — si son grandes en
  volumen, es una oportunidad de mejorar el registro de datos en Clientify,
  no necesariamente un problema de canal.
""".strip()

SUPUESTOS_GESTION_COMERCIAL = """
SUPUESTOS a confirmar con el negocio (si alguno es incorrecto, corregilo
en este archivo):
- SUPUESTO: no hay una meta oficial de leads/cierres por día — evaluá el
  ritmo diario contra el propio promedio/mejor/peor día del mismo payload.
- SUPUESTO: "Sin diligenciar" en motivos de no cierre es un motivo NO
  registrado por el asesor, no una categoría de negocio real — si es
  grande en volumen, es una oportunidad de mejorar el registro de datos,
  no necesariamente una causa de no cierre en sí misma.
""".strip()
