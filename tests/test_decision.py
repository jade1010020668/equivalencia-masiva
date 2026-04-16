"""
Tests del motor de decisión — verifica que la compuerta AND del notebook se
aplica correctamente sobre los resultados de aspectos SBERT.

Estos tests NO requieren cargar SBERT: construimos AspectosResult sintéticos
con los scores que el motor semántico habría devuelto.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.decision import decidir  # noqa: E402
from core.semantic import AspectoResult, AspectosResult, TipoExperiencia  # noqa: E402


def _build_aspectos(
    *,
    funciones: float = 0.80,
    estudio: float = 0.80,
    comp_lab: float = 0.80,
    comp_comp: float = 0.80,
    experiencia: float = 0.80,
    nivel_pasa: bool = True,
    salario_pasa: bool = True,
) -> AspectosResult:
    """Helper: construye un AspectosResult con scores controlados."""
    return AspectosResult(
        funciones=AspectoResult(cobertura=funciones),
        estudio=AspectoResult(cobertura=estudio),
        comp_lab=AspectoResult(cobertura=comp_lab),
        comp_comp=AspectoResult(cobertura=comp_comp),
        experiencia=AspectoResult(cobertura=experiencia),
        tipo_exp_base=TipoExperiencia.LABORAL,
        tipo_exp_destino=TipoExperiencia.LABORAL,
        nivel_pasa=nivel_pasa,
        nivel_msg="ok" if nivel_pasa else "distinto",
        salario_pasa=salario_pasa,
        salario_msg="ok" if salario_pasa else "distinto",
    )


# -------------------------------------------------------------------------
# Casos equivalentes
# -------------------------------------------------------------------------


def test_todos_los_aspectos_pasan_con_requisitos_incluidos() -> None:
    """Todo por encima de los umbrales → EQUIVALENTE."""
    aspectos = _build_aspectos(funciones=0.85, estudio=0.80, comp_lab=0.75, comp_comp=0.70)
    d = decidir(aspectos, incluir_requisitos=True)
    assert d.es_equivalente is True
    assert d.clasificacion == "EQUIVALENTE"
    assert d.pasa_funciones and d.pasa_estudio and d.pasa_comp_lab and d.pasa_comp_comp
    assert d.razones == []


def test_solo_funciones_sin_incluir_requisitos_es_equivalente() -> None:
    """Con incluir_requisitos=False, solo funciones + gating importa."""
    aspectos = _build_aspectos(funciones=0.65, estudio=0.0, comp_lab=0.0, comp_comp=0.0)
    d = decidir(aspectos, incluir_requisitos=False)
    assert d.es_equivalente is True
    assert d.score == aspectos.funciones.cobertura  # Solo pesa funciones


# -------------------------------------------------------------------------
# Casos no equivalentes
# -------------------------------------------------------------------------


def test_nivel_no_pasa_es_no_equivalente() -> None:
    aspectos = _build_aspectos(nivel_pasa=False)
    aspectos.nivel_msg = "Niveles diferentes"
    d = decidir(aspectos, incluir_requisitos=True)
    assert d.es_equivalente is False
    assert "Niveles diferentes" in " | ".join(d.razones)


def test_salario_no_pasa_es_no_equivalente() -> None:
    aspectos = _build_aspectos(salario_pasa=False)
    aspectos.salario_msg = "Grados diferentes"
    d = decidir(aspectos, incluir_requisitos=True)
    assert d.es_equivalente is False


def test_funciones_debajo_del_umbral_es_no_equivalente() -> None:
    aspectos = _build_aspectos(funciones=0.55)  # 55% < 60% default
    d = decidir(aspectos, incluir_requisitos=True)
    assert d.es_equivalente is False
    assert any("Funciones" in r for r in d.razones)


def test_estudio_debajo_del_umbral_con_requisitos_es_no_equivalente() -> None:
    aspectos = _build_aspectos(estudio=0.65)  # 65% < 70% default
    d = decidir(aspectos, incluir_requisitos=True)
    assert d.es_equivalente is False
    assert any("Estudio" in r for r in d.razones)


def test_estudio_debajo_sin_incluir_requisitos_es_equivalente() -> None:
    """Si no incluimos requisitos, estudio bajo NO descalifica."""
    aspectos = _build_aspectos(estudio=0.50)
    d = decidir(aspectos, incluir_requisitos=False)
    assert d.es_equivalente is True


def test_comp_laborales_debajo_con_requisitos_es_no_equivalente() -> None:
    aspectos = _build_aspectos(comp_lab=0.60)  # 60% < 65% default
    d = decidir(aspectos, incluir_requisitos=True)
    assert d.es_equivalente is False
    assert any("Laborales" in r for r in d.razones)


def test_comp_comportamentales_debajo_con_requisitos_es_no_equivalente() -> None:
    aspectos = _build_aspectos(comp_comp=0.60)  # 60% < 65% default
    d = decidir(aspectos, incluir_requisitos=True)
    assert d.es_equivalente is False
    assert any("Comportamentales" in r for r in d.razones)


# -------------------------------------------------------------------------
# Score ponderado
# -------------------------------------------------------------------------


def test_score_ponderado_con_requisitos_default_pesos() -> None:
    """
    Con pesos default (func=0.80, est=0.20, comp=0.00):
      score = (0.80 * 0.80 + 0.20 * 0.50 + 0.00 + 0.00) / (0.80 + 0.20 + 0 + 0)
            = (0.64 + 0.10) / 1.0
            = 0.74
    """
    aspectos = _build_aspectos(funciones=0.80, estudio=0.50, comp_lab=0.0, comp_comp=0.0)
    d = decidir(aspectos, incluir_requisitos=True)
    assert abs(d.score - 0.74) < 1e-9


def test_score_sin_incluir_requisitos_es_solo_funciones() -> None:
    aspectos = _build_aspectos(funciones=0.72, estudio=0.0, comp_lab=0.0, comp_comp=0.0)
    d = decidir(aspectos, incluir_requisitos=False)
    assert d.score == 0.72


# -------------------------------------------------------------------------
# Umbrales custom
# -------------------------------------------------------------------------


def test_umbrales_custom_afectan_decision() -> None:
    """Si subimos el umbral de funciones a 90%, un 85% deja de ser equivalente."""
    aspectos = _build_aspectos(funciones=0.85)
    d_default = decidir(aspectos, incluir_requisitos=True)  # umbral_func=0.60
    d_strict = decidir(aspectos, incluir_requisitos=True, umbral_funciones=0.90)
    assert d_default.es_equivalente is True
    assert d_strict.es_equivalente is False
