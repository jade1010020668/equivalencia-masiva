"""
Agrupamiento de empleos base (4.0) con sus listas candidatas.

Traducción 1:1 del TypeScript en copy-of-criterio-base.zip::services/excelProcessor.ts
a Python. Mantenemos los mismos nombres de grupo (`ENTIDAD - P - B - OPEC`) para que
los resultados sean comparables 1:1 con la app React original.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import IO, Union

import pandas as pd

from config import ID_COLUMN, REQUIRED_COLUMNS


@dataclass
class GrupoBase:
    """Un empleo base 4.0 junto con las listas de elegibles que tienen su mismo grado."""

    nombre: str
    entidad: str
    nivel: str
    grado: str
    base: pd.Series
    listas: pd.DataFrame
    # is_lonely = la base no tiene ninguna lista candidata con el mismo grado
    is_lonely: bool = field(init=False)

    def __post_init__(self) -> None:
        self.is_lonely = self.listas.empty


# --- Helpers portados de excelProcessor.ts ---

def _get_nivel_inicial(nivel: str) -> str:
    """Replica getNivelInitial() del TS. Mapea nivel jerárquico a su letra inicial."""
    if not nivel:
        return "X"
    lower = nivel.lower().strip()
    if "asistencial" in lower:
        return "A"
    if "profesional" in lower:
        return "P"
    if "tecnico" in lower or "técnico" in lower:
        return "T"
    return nivel[0].upper()


def _normalize_grade(grado) -> str:
    """Replica normalizeGrade() del TS. Intenta convertir a int si es posible."""
    if grado is None:
        return ""
    if isinstance(grado, float) and pd.isna(grado):
        return ""
    s = str(grado).strip()
    if not s:
        return ""
    try:
        return str(int(float(s)))
    except ValueError:
        return s.upper()


def _modalidad_clean(valor) -> str:
    """Normaliza el campo modalidad a string en mayúscula sin espacios al borde."""
    if valor is None:
        return ""
    if isinstance(valor, float) and pd.isna(valor):
        return ""
    # Numérico: convertir a float para que int(4) → "4.0" igual que float(4.0)
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return str(float(valor))
    return str(valor).strip().upper()


def validar_columnas(df: pd.DataFrame) -> list[str]:
    """Devuelve la lista de columnas requeridas que faltan (vacío si todo OK)."""
    return [c for c in REQUIRED_COLUMNS if c not in df.columns]


def agrupar_dataframe(df: pd.DataFrame) -> list[GrupoBase]:
    """
    Replica el pipeline de processExcelFile() del TS:

      1. Agrupa por (nombre_entidad, Nivel Jerárquico).
      2. Separa filas LISTAS vs modalidad '4.0' dentro de cada grupo.
      3. Por cada base 4.0, toma las LISTAS con grado exacto.
      4. Genera nombre único '{Entidad} - {Inicial Nivel} - B - {OPEC}'.
      5. Ordena alfabéticamente por nombre de grupo (como el TS).
    """
    grupos: list[GrupoBase] = []

    # Nos aseguramos que las columnas clave existan
    if not {"nombre_entidad", "Nivel Jerárquico", "modalidad"}.issubset(df.columns):
        return grupos

    df = df.copy()
    df["__modalidad_clean__"] = df["modalidad"].apply(_modalidad_clean)
    df["__grado_norm__"] = df["Grado"].apply(_normalize_grade)

    # Filtramos filas con entidad o nivel vacíos (el TS también las salta).
    mask_valid = (
        df["nombre_entidad"].astype(str).str.strip().ne("")
        & df["Nivel Jerárquico"].astype(str).str.strip().ne("")
    )
    df = df[mask_valid]

    # Ordenamos por entidad + nivel para iteración determinista (igual que el TS).
    for (entidad, nivel), grupo_df in df.groupby(
        [df["nombre_entidad"].str.strip(), df["Nivel Jerárquico"].str.strip()],
        sort=True,
    ):
        listas = grupo_df[grupo_df["__modalidad_clean__"] == "LISTAS"]
        bases = grupo_df[grupo_df["__modalidad_clean__"] == "4.0"]

        if bases.empty:
            continue

        # El TS itera `baseJobs.forEach((base, index) => ...)`
        bases_list = list(bases.iterrows())
        total_bases = len(bases_list)

        for index, (_, base_row) in enumerate(bases_list):
            target_grade = _normalize_grade(base_row["Grado"])
            matching = listas[listas["__grado_norm__"] == target_grade]

            opec = base_row.get(ID_COLUMN, "SN")
            if opec is None or (isinstance(opec, float) and pd.isna(opec)):
                opec = "SN"

            unique_id = f" ({index + 1})" if total_bases > 1 else ""
            nombre = f"{entidad} - {_get_nivel_inicial(nivel)} - B - {opec}{unique_id}"

            # Quitamos las columnas internas antes de exponer la base/listas al resto.
            base_clean = base_row.drop(labels=["__modalidad_clean__", "__grado_norm__"])
            listas_clean = matching.drop(columns=["__modalidad_clean__", "__grado_norm__"])

            grupos.append(
                GrupoBase(
                    nombre=nombre,
                    entidad=entidad,
                    nivel=nivel,
                    grado=target_grade,
                    base=base_clean,
                    listas=listas_clean,
                )
            )

    grupos.sort(key=lambda g: g.nombre)
    return grupos


def agrupar_excel(source: Union[str, IO[bytes]]) -> tuple[list[GrupoBase], list[str]]:
    """
    Wrapper alto nivel: lee Excel -> valida columnas -> agrupa.

    Devuelve (lista_de_grupos, lista_de_columnas_faltantes).
    Si faltan columnas requeridas, devuelve ([], faltantes) sin procesar.
    """
    df = pd.read_excel(source)
    faltantes = validar_columnas(df)
    if faltantes:
        return [], faltantes
    return agrupar_dataframe(df), []
