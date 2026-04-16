"""
Tests del agrupador — verifica que replica el pipeline del React excelProcessor.ts.

Usamos un DataFrame sintético con 2 entidades, 2 niveles y una mezcla de filas
4.0/LISTAS para cubrir los casos que el TS maneja: agrupamiento por
(entidad, nivel), filtro por grado exacto, y sufijo `(1)`, `(2)` cuando hay
múltiples bases en el mismo grupo.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# Permitir `python -m pytest tests/` desde la raíz
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.grouping import agrupar_dataframe, _get_nivel_inicial, _normalize_grade  # noqa: E402


def _base_df() -> pd.DataFrame:
    """Fixture: 4 filas — 1 base 4.0 + 2 listas compatibles + 1 lista con grado distinto."""
    return pd.DataFrame(
        {
            "No. OPEC": [100, 200, 300, 400],
            "Código": [477, 477, 477, 312],
            "Denominación": ["Auxiliar", "Auxiliar", "Auxiliar", "Técnico"],
            "Grado": [10, 10, 10, 12],
            "Nivel Jerárquico": ["Asistencial", "Asistencial", "Asistencial", "Asistencial"],
            "Orden": ["Nacional"] * 4,
            "Naturaleza Jurídica": ["Ministerio"] * 4,
            "Salario": [1_500_000, 1_500_000, 1_500_000, 1_800_000],
            "Requisitos Estudio": ["Bachiller"] * 4,
            "Requisitos Experiencia": ["12 meses experiencia laboral"] * 4,
            "Funciones": ["Apoyar tareas administrativas"] * 4,
            "modalidad": ["4.0", "LISTAS", "LISTAS", "LISTAS"],
            "nombre_entidad": ["Alcaldía de Cali"] * 4,
        }
    )


def test_helpers_basicos() -> None:
    """Los helpers replican getNivelInitial() y normalizeGrade() del TS."""
    assert _get_nivel_inicial("Asistencial") == "A"
    assert _get_nivel_inicial("profesional") == "P"
    assert _get_nivel_inicial("Técnico") == "T"
    assert _get_nivel_inicial("otro") == "O"
    assert _get_nivel_inicial("") == "X"

    assert _normalize_grade(10) == "10"
    assert _normalize_grade("10") == "10"
    assert _normalize_grade(10.0) == "10"
    assert _normalize_grade("A") == "A"
    assert _normalize_grade(None) == ""


def test_agrupamiento_un_grupo_con_dos_listas_validas() -> None:
    """La base 4.0 con grado 10 agrupa las 2 listas con grado 10, no la de grado 12."""
    df = _base_df()
    grupos = agrupar_dataframe(df)

    assert len(grupos) == 1
    g = grupos[0]
    assert g.nombre == "Alcaldía de Cali - A - B - 100"
    assert g.entidad == "Alcaldía de Cali"
    assert g.nivel == "Asistencial"
    assert g.grado == "10"
    assert len(g.listas) == 2
    assert set(g.listas["No. OPEC"].tolist()) == {200, 300}
    assert g.is_lonely is False


def test_agrupamiento_base_huerfana() -> None:
    """Una base 4.0 sin listas del mismo grado queda marcada como is_lonely."""
    df = _base_df()
    df = df[df["No. OPEC"].isin([100])]  # solo la base 4.0, sin listas
    grupos = agrupar_dataframe(df)
    assert len(grupos) == 1
    assert grupos[0].is_lonely is True
    assert len(grupos[0].listas) == 0


def test_agrupamiento_multiples_bases_mismo_grupo_genera_sufijo() -> None:
    """
    Cuando hay 2 bases 4.0 en el mismo (entidad, nivel), el TS genera nombres
    con sufijo ' (1)' y ' (2)'. El porting debe replicar eso.
    """
    df = _base_df()
    # Convertimos la lista OPEC=400 en una segunda base 4.0 con grado 10
    df.loc[df["No. OPEC"] == 400, "modalidad"] = "4.0"
    df.loc[df["No. OPEC"] == 400, "Grado"] = 10

    grupos = agrupar_dataframe(df)
    nombres = sorted(g.nombre for g in grupos)
    # Ambas bases tienen OPEC distintos pero ocupan la misma entidad+nivel,
    # así que esperamos sufijos (1) y (2).
    assert any("(1)" in n for n in nombres)
    assert any("(2)" in n for n in nombres)
    assert len(grupos) == 2


def test_agrupamiento_respeta_entidad_distinta() -> None:
    """Dos entidades distintas generan grupos distintos aunque coincidan en nivel/grado."""
    df = _base_df()
    df2 = df.copy()
    df2["nombre_entidad"] = "Gobernación del Valle"
    df2["No. OPEC"] = df2["No. OPEC"] + 1000
    combined = pd.concat([df, df2], ignore_index=True)

    grupos = agrupar_dataframe(combined)
    entidades = {g.entidad for g in grupos}
    assert entidades == {"Alcaldía de Cali", "Gobernación del Valle"}
    assert len(grupos) == 2
