# Clientify Analyzer — contexto del proyecto

## Qué es esto

Software de análisis comercial para una firma legal de inmigración. Carga contactos de Clientify (vía Excel exportado o por API directamente) y muestra un dashboard con los KPIs del mes en tarjetas tipo Power BI.

## Stack

- **Streamlit** para la UI (`streamlit run app.py`)
- **pandas** para manipulación de datos
- **openpyxl / xlrd** para leer archivos Excel
- **requests** para la API de Clientify (futuro)
- **plotly** para gráficos
- **python-dotenv** para variables de entorno
- **pytest** para tests

Python 3.11+ recomendado.

## Arquitectura — separación en 3 capas

Regla de oro: **la lógica de negocio no sabe nada de Streamlit ni de Excel**. Esto permite cambiar la UI o la fuente de datos sin reescribir nada más.

```
src/
├── data_sources/   capa de datos (Excel hoy, API Clientify mañana)
├── analytics/      lógica de negocio pura (recibe DataFrame, devuelve KPIs)
└── ui/             solo presentación con Streamlit
```

- **`data_sources/`** — todas las clases heredan de `ContactsDataSource` (en `base.py`) y devuelven un DataFrame con el mismo esquema. Hoy hay `ExcelContactsLoader`, falta completar `ClientifyAPIClient`.
- **`analytics/`** — funciones puras de pandas. No importan Streamlit. Fáciles de testear.
- **`ui/`** — solo componentes Streamlit. Si mañana se migra a FastAPI + React, esta carpeta se descarta y el resto sirve igual.

## KPIs que calcula la app

Sobre los registros del **mes seleccionado** (filtrados por la columna `creado`):

| KPI | Definición |
|---|---|
| Creados del mes | Conteo total de registros del mes |
| Asignados | Registros con `propietario` no nulo |
| Calificados | Registros con `estado` ∈ `QUALIFIED_STATES` (ver `config/settings.py`) |
| Cierres por pautas | Registros con `Origen de la pauta` ∈ {Facebook, Instagram} y al menos un cierre |
| Total cierres (1+2+3+4) | Cierres con fecha en el mes (1ro + 2do + 3ro + 4to) |
| % Calificación | Calificados / Asignados |
| Eficiencia Total | Total cierres / Total leads del mes |
| Eficiencia comerciales | Cierres de redes / Total leads de redes |

"Redes" = leads con `canal online == 'paid social'` o `Origen de la pauta` no nulo (Facebook/Instagram).

## Esquema del DataFrame (columnas clave del export de Clientify)

| Columna | Tipo | Notas |
|---|---|---|
| `creado` | datetime | Fecha de creación del lead |
| `propietario` | string | Comercial asignado |
| `estado` | string | Ver `QUALIFIED_STATES` y `UNQUALIFIED_STATES` |
| `canal online` | string | `paid social`, `inbox-referral`, `inbox` |
| `origen contacto` | string | `inbox_whatsapp`, `inbox_instagram`, etc. |
| `Origen de la pauta` | string | `Facebook`, `Instagram`, `No Aplica`. A veces viene como `['Facebook']` (string con lista) |
| `Cantidad de cierres` | float | 1.0, 2.0, 3.0, 4.0 |
| `Fecha de cierre` | datetime | Primer cierre |
| `Fecha de segundo cierre` | datetime | |
| `Fecha de tercer cierre` | datetime | |
| `Fecha de 4to cierre` | datetime | |

`ExcelContactsLoader._normalize()` ya hace el parsing de fechas y la limpieza de strings (lower, strip).

## Cuidados al escribir código

- **No mezclar capas.** Si estás en `analytics/`, no importes nada de `streamlit` ni de `data_sources/`.
- **DataFrames inmutables hacia adentro.** Las funciones de `analytics/` no deben mutar el DF de entrada — siempre `.copy()` o operar en cadena.
- **Estados normalizados.** Toda comparación de strings se hace en lower + strip — eso ya lo hace el loader. Si agregás un nuevo estado a la lógica, agregalo en `config/settings.py`, no hardcodeado en `metrics.py`.
- **Tests primero para `analytics/`.** Cualquier KPI nuevo debe tener su test en `tests/test_metrics.py` con un DataFrame de fixture.

## Comandos frecuentes

```bash
# Correr la app
streamlit run app.py

# Tests
pytest tests/ -v

# Crear/activar venv
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

## Roadmap

- [ ] Completar `ClientifyAPIClient.load()` con paginación real y mapeo de campos
- [ ] Comparación con período anterior (deltas tipo +23, -5, etc.)
- [ ] Gráficos de evolución mensual (plotly) en `ui/charts.py`
- [ ] Filtro por comercial / por canal
- [ ] Exportar el análisis a PDF o Excel
- [ ] Login / multi-usuario
