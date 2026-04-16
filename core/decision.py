"""
Motor de decisión — port fiel del notebook mismo_grado_.ipynb.

El notebook NO usa cascada ni lógica compleja: es una compuerta AND pura sobre
coberturas semánticas SBERT. Esta versión replica eso exactamente para que
los resultados coincidan.

Lógica del notebook (on_analizar_click):

    pasa_f = cobertura_funciones   >= umbral_funciones
    pasa_e = cobertura_estudio     >= umbral_estudio
    pasa_l = cobertura_comp_lab    >= umbral_comp
    pasa_c = cobertura_comp_comp   >= umbral_comp

    es_equivalente = nivel.pasa AND salario.pasa AND pasa_f
    if incluir_requisitos:
        es_equivalente = es_equivalente AND pasa_e AND pasa_l AND pasa_c

    score_ponderado = weighted_avg(funciones, estudio, comp_lab, comp_comp)

Nota: si los dos textos de un aspecto están vacíos, eval_crit del notebook
devuelve pasa=True (con cobertura 1.0). Si sólo uno está vacío, devuelve
pasa=False. Eso ya lo maneja `_calc_aspecto` en semantic.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from config import (
    INCLUIR_REQUISITOS_EN_DECISION,
    UMBRAL_DECISION_COMP,
    UMBRAL_DECISION_ESTUDIO,
    UMBRAL_DECISION_FUNCIONES,
    WEIGHT_COMP_COMP,
    WEIGHT_COMP_LAB,
    WEIGHT_ESTUDIO,
    WEIGHT_FUNCIONES,
)
from core.semantic import AspectosResult


@dataclass
class DecisionFinal:
    """Veredicto final del análisis — refleja exactamente la salida del notebook."""

    es_equivalente: bool
    clasificacion: str  # "EQUIVALENTE" | "NO_EQUIVALENTE"
    score: float  # equivalence_score del notebook
    razones: list[str] = field(default_factory=list)

    pasa_funciones: bool = False
    pasa_estudio: bool = False
    pasa_comp_lab: bool = False
    pasa_comp_comp: bool = False


def _eval_crit(
    cobertura: float,
    umbral: float,
    label: str,
    error: Optional[str],
) -> tuple[bool, Optional[str]]:
    """notebook: eval_crit simplificado (sin dependencias de params_dict)."""
    if error:
        return False, f"Error en {label}: {error[:60]}..."
    pasa = cobertura >= umbral
    razon = None if pasa else f"Similitud {cobertura:.1%} < umbral ({umbral:.1%}) para {label}."
    return pasa, razon


def decidir(
    aspectos: AspectosResult,
    *,
    umbral_funciones: float = UMBRAL_DECISION_FUNCIONES,
    umbral_estudio: float = UMBRAL_DECISION_ESTUDIO,
    umbral_comp: float = UMBRAL_DECISION_COMP,
    incluir_requisitos: bool = INCLUIR_REQUISITOS_EN_DECISION,
    peso_funciones: float = WEIGHT_FUNCIONES,
    peso_estudio: float = WEIGHT_ESTUDIO,
    peso_comp_lab: float = WEIGHT_COMP_LAB,
    peso_comp_comp: float = WEIGHT_COMP_COMP,
) -> DecisionFinal:
    """
    Aplica la compuerta AND del notebook sobre los resultados de aspectos.
    Devuelve `DecisionFinal` con clasificación, score y razones de no equivalencia.
    """
    razones: list[str] = []

    # Gating: nivel y salario (del notebook comparar_niveles/comparar_salarios)
    if not aspectos.nivel_pasa:
        razones.append(aspectos.nivel_msg)
    if not aspectos.salario_pasa:
        razones.append(aspectos.salario_msg)

    # Cada aspecto se evalúa como eval_crit
    pasa_f, razon_f = _eval_crit(
        aspectos.funciones.cobertura, umbral_funciones, "Funciones", aspectos.funciones.error
    )
    pasa_e, razon_e = _eval_crit(
        aspectos.estudio.cobertura, umbral_estudio, "Requisitos Estudio", aspectos.estudio.error
    )
    pasa_l, razon_l = _eval_crit(
        aspectos.comp_lab.cobertura, umbral_comp, "Comp. Laborales", aspectos.comp_lab.error
    )
    pasa_c, razon_c = _eval_crit(
        aspectos.comp_comp.cobertura, umbral_comp, "Comp. Comportamentales", aspectos.comp_comp.error
    )

    if razon_f:
        razones.append(razon_f)
    if razon_e:
        razones.append(razon_e)
    if razon_l:
        razones.append(razon_l)
    if razon_c:
        razones.append(razon_c)

    # Compuerta AND — IDÉNTICA al notebook
    es_equiv = aspectos.nivel_pasa and aspectos.salario_pasa and pasa_f
    if incluir_requisitos:
        es_equiv = es_equiv and pasa_e and pasa_l and pasa_c

    # Score ponderado — IDÉNTICO al notebook
    s_f = aspectos.funciones.cobertura
    s_e = aspectos.estudio.cobertura
    s_l = aspectos.comp_lab.cobertura
    s_c = aspectos.comp_comp.cobertura

    if incluir_requisitos:
        w_sum = (
            s_f * peso_funciones
            + s_e * peso_estudio
            + s_l * peso_comp_lab
            + s_c * peso_comp_comp
        )
        w_total = peso_funciones + peso_estudio + peso_comp_lab + peso_comp_comp
        score = w_sum / w_total if w_total > 0 else 0.0
    else:
        score = s_f

    return DecisionFinal(
        es_equivalente=es_equiv,
        clasificacion="EQUIVALENTE" if es_equiv else "NO_EQUIVALENTE",
        score=score,
        razones=sorted(set(r for r in razones if r)),
        pasa_funciones=pasa_f,
        pasa_estudio=pasa_e,
        pasa_comp_lab=pasa_l,
        pasa_comp_comp=pasa_c,
    )
