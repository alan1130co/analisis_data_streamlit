# Dashboard de Análisis de Datos - Soluciones Migratorias

Software de análisis de data para la toma de mejores decisiones 💻📈

## Stack

Python · Streamlit · Pandas · Plotly

## Correr localmente

1. Clonar el repo
2. Crear venv: `python -m venv .venv`
3. Activar: `.venv\Scripts\activate` (Windows)
4. Instalar: `pip install -r requirements.txt`
5. Crear `.streamlit/secrets.toml` con la contraseña (ver `.streamlit/secrets.toml.example`)
6. Correr: `streamlit run app.py`

## Estructura

- `src/analytics/` — Lógica de cálculo
- `src/data_sources/` — Loaders
- `src/ui/sections/` — Componentes UI
- `tests/` — Tests pytest

## Autor

Alan Coneo · Neiva, Colombia
