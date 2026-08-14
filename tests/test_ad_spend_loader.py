"""Tests para AdSpendLoader — lectura de CSV/Excel de Facturación de Meta Ads."""
import io

from src.data_sources.ad_spend_loader import AdSpendLoader


def _make_uploaded(content: str, name: str = "facturacion.csv"):
    buf = io.BytesIO(content.encode("utf-8"))
    buf.name = name
    return buf


def test_csv_con_metainformacion_salta_encabezado_falso():
    contenido = (
        "Metainformación del reporte\n"
        "Cuenta publicitaria: 123456789\n"
        "Rango de fechas: 01/04/2026 - 30/04/2026\n"
        "\n"
        "Fecha,Divisa,Importe,Identificador de la transacción\n"
        "01/04/2026,USD,\"100,00\",TX1\n"
        "02/04/2026,USD,\"200,00\",TX2\n"
    )
    loader = AdSpendLoader(_make_uploaded(contenido))
    df = loader.load()
    assert list(df.columns) == ["Fecha", "Divisa", "Importe", "Identificador de la transacción"]
    assert len(df) == 2


def test_csv_sin_metainformacion_funciona_igual():
    contenido = "Fecha,Divisa,Importe\n01/04/2026,USD,100\n"
    loader = AdSpendLoader(_make_uploaded(contenido))
    df = loader.load()
    assert len(df) == 1


def test_csv_con_alias_de_columnas_se_normaliza():
    contenido = "Fecha de inicio del informe,Moneda,Amount spent (USD)\n01/04/2026,USD,100\n"
    loader = AdSpendLoader(_make_uploaded(contenido))
    df = loader.load()
    assert set(["Fecha", "Divisa", "Importe"]).issubset(df.columns)
