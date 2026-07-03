import unicodedata
import pandas as pd
import gender_guesser.detector as gender
from src.analytics.metrics import is_marketing, _is_valid_closure_estado


_detector = gender.Detector(case_sensitive=False)


def _normalizar(s: str) -> str:
    """Lowercase + strip diacritics."""
    return unicodedata.normalize("NFD", s.lower()).encode("ascii", "ignore").decode()


NOMBRES_HOMBRE = {
    "hayler", "norbey", "obel", "faiver", "jonny", "leider", "leyder",
    "neider", "neyder", "brayder", "brayan", "brayhan", "breiner", "deiner",
    "deivinson", "deivys", "deilon", "dorian", "edward", "edwar",
    "elder", "elver", "fabricio", "fabian", "fernan", "frander",
    "gerson", "geison", "gehiner", "gehinson", "helver", "ilder",
    "jefry", "jeisson", "jhoel", "jhojan", "jhonatan", "jhonier",
    "jhormar", "jhostin", "jhostyn", "joiner", "jorbeli", "jordi",
    "joriman", "jovanny", "juliam", "julivan", "kenyer", "kenyo",
    "lainer", "leiber", "leiner", "leyber", "marlon", "naidher",
    "ovidio", "oyer", "railan", "royer", "sebas", "smith", "stiven",
    "steven", "sthick", "tarek", "urvan", "vladimir", "yader", "yamil",
    "yamilson", "yelfri", "yerald", "yerson", "yesith", "yibran",
    "yobani", "yolfran", "yorhan", "yorlan", "yorman", "yose", "yostin",
    "yover", "ider", "edinson", "esteybar", "estiwar", "estyver",
}

NOMBRES_MUJER = {
    "ingrith", "anyi", "paquita", "udelfa", "yanira", "yorlani", "anyely",
    "alixon", "arelys", "berenice", "brisilda", "dailin", "dailyn", "dairys",
    "daritza", "deyani", "dilyana", "edenis", "edileinis", "eilen", "einoska",
    "eliana", "eliangelis", "eliangely", "elismar", "elismeira", "evelin",
    "evelyn", "geilyn", "geinis", "geyselis", "glenmar", "herly", "joselin",
    "joselyne", "juleidy", "kahely", "karilyn", "kaylin", "keiber", "keidy",
    "kerlly", "leidy", "leidi", "leslin", "leyanis", "leylin", "lismar",
    "lismeida", "lourdes", "ludis", "luiyer", "magdi", "marjuri", "marjorie",
    "maryori", "maryury", "melyn", "meliyer", "mileidy", "miverlys", "neiyer",
    "nelibeth", "neimar", "niceth", "nieira", "nileidys", "nora", "orlymar",
    "oselys", "raylyn", "reybellys", "riarvellis", "roxelys", "sariannys",
    "sariny", "sasha", "sherlys", "suheyli", "syaily", "taneidy", "vetzaida",
    "virleizys", "yaceli", "yadira", "yainerit", "yamilex", "yamilet",
    "yamileth", "yanelis", "yanelys", "yarisbel", "yarvelys", "yarisleidy",
    "yelitza", "yenibel", "yerlin", "yesibel", "yileini", "yilixa", "yiseth",
    "yliana", "yodanis", "yohanys", "yolimar", "yornelys", "yorsidys",
    "yosveidy", "yulianny", "yusneidi",
}

# Sufijos ordenados de más largo a más corto para evitar falsos positivos
_SUFIJOS_MUJER = (
    "elys", "alys", "ilys", "olys", "deys", "eidy", "leidy",
    "ana", "ina", "ena", "lia", "nia", "tia", "ria", "lla", "lly",
    "eth", "lyn", "lin",
    "esa", "isa", "osa", "usa",
    "ela", "ila", "ola",
    "uli", "ory", "iry", "ery",
    "tte", "thy",
    "a",
)

_SUFIJOS_HOMBRE = (
    "ardo", "ando", "endo", "indo",
    "der", "ber", "ver", "mer", "ner", "ler", "ger",
    "son", "ton", "ron",
    "ian", "yan", "ran",
    "uel", "iel", "ael", "yel",
    "ero", "io",
    "or", "er", "us", "as", "is", "os",
    "o",
)


def _detectar_genero(nombre_completo) -> str:
    """Detecta género. Cascada de reglas — NUNCA devuelve 'No identificado'."""
    if pd.isna(nombre_completo) or not str(nombre_completo).strip():
        return "Hombre"

    primer_nombre = _normalizar(str(nombre_completo).strip().split()[0])

    if not primer_nombre or primer_nombre in {"nan", "none", "no", ".", "name"}:
        return "Hombre"

    # Paso 1: listas explícitas (nombres latinos que gender-guesser no reconoce)
    if primer_nombre in NOMBRES_HOMBRE:
        return "Hombre"
    if primer_nombre in NOMBRES_MUJER:
        return "Mujer"

    # Paso 2: gender-guesser para nombres internacionales/estándar
    resultado = _detector.get_gender(primer_nombre)
    if resultado in {"male", "mostly_male"}:
        return "Hombre"
    if resultado in {"female", "mostly_female"}:
        return "Mujer"

    # Paso 3: terminaciones típicas femeninas
    for suf in _SUFIJOS_MUJER:
        if primer_nombre.endswith(suf):
            return "Mujer"

    # Paso 4: terminaciones típicas masculinas
    for suf in _SUFIJOS_HOMBRE:
        if primer_nombre.endswith(suf):
            return "Hombre"

    # Paso 5: default — hombre es la categoría mayoritaria en los datos del negocio
    return "Hombre"


def closures_by_gender(
    df_full: pd.DataFrame,
    year: int,
    month: int,
    team: str = "Todos",
) -> pd.DataFrame:
    """Distribución de cierres del mes por género (detectado desde nombre).

    Columns: Género, Cantidad, Porcentaje
    Ordenado: Hombre, Mujer
    """
    if df_full.empty:
        return pd.DataFrame(columns=["Género", "Cantidad", "Porcentaje"])

    closure_cols = [
        "Fecha de cierre", "Fecha de segundo cierre",
        "Fecha de tercer cierre", "Fecha de 4to cierre",
    ]

    active = df_full.apply(_is_valid_closure_estado, axis=1)
    rows = []
    for col in closure_cols:
        if col not in df_full.columns:
            continue
        s = pd.to_datetime(df_full[col], errors="coerce")
        mask = (s.dt.year == year) & (s.dt.month == month) & active
        sub = df_full[mask]
        if sub.empty:
            continue
        for _, row in sub.iterrows():
            es_mkt = is_marketing(row)
            if team == "Marketing (pautas)" and not es_mkt:
                continue
            if team == "Referidos" and es_mkt:
                continue

            nombre = row.get("nombre", "")
            genero = _detectar_genero(nombre)
            rows.append({"Género": genero})

    if not rows:
        return pd.DataFrame(columns=["Género", "Cantidad", "Porcentaje"])

    out = pd.DataFrame(rows)["Género"].value_counts().reset_index()
    out.columns = ["Género", "Cantidad"]
    total = int(out["Cantidad"].sum())
    out["Porcentaje"] = (out["Cantidad"] / total * 100).round(1)

    orden = {"Hombre": 0, "Mujer": 1}
    out["__sort"] = out["Género"].map(orden).fillna(99)
    out = out.sort_values("__sort").drop(columns="__sort").reset_index(drop=True)
    return out


def available_periods(df_full: pd.DataFrame) -> list[tuple[int, int]]:
    """Periodos (año, mes) con cierres."""
    periods = set()
    for col in ["Fecha de cierre", "Fecha de segundo cierre",
                "Fecha de tercer cierre", "Fecha de 4to cierre"]:
        if col not in df_full.columns:
            continue
        s = pd.to_datetime(df_full[col], errors="coerce").dropna()
        for ts in s:
            periods.add((ts.year, ts.month))
    return sorted(periods, reverse=True)
