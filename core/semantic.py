"""
Motor semántico — port fiel de mismo_grado_.ipynb (Colab notebook del Despacho).

REGLA: este módulo debe producir los MISMOS scores y clasificaciones que el
notebook original cuando se corre sobre los mismos pares (base, lista). Si
algo difiere, es un bug de este módulo.

Diferencias intencionales respecto al notebook:
  1. Procesamiento MASIVO (no UI ipywidgets) — iteramos todos los pares.
  2. Batching de embeddings — encode una sola vez por texto único, cachea.
  3. Lematización spaCy omitida por defecto (el notebook también la trae
     desactivada en `lemma_box.value = False`).
  4. Sólo cargamos 1 modelo SBERT a la vez (el primario de la config).

Todo lo demás es idéntico al notebook.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from typing import Optional

import numpy as np
import pandas as pd

from config import (
    ELIMINAR_DUPLICADOS,
    INCLUIR_REQUISITOS_EN_DECISION,
    LEMATIZAR,
    MIN_WORDS_PER_ITEM,
    NORMALIZAR_TEXTO,
    PESO_COSENO,
    PESO_JACCARD,
    SALARY_DIFF_PERCENTAGE_THRESHOLD,
    SBERT_MODEL_NAME,
    UMBRAL_DECISION_COMP,
    UMBRAL_DECISION_ESTUDIO,
    UMBRAL_DECISION_FUNCIONES,
    USAR_JACCARD,
    WEIGHT_COMP_COMP,
    WEIGHT_COMP_LAB,
    WEIGHT_ESTUDIO,
    WEIGHT_FUNCIONES,
)

# =========================================================================
# Tipos (enum espejo del notebook)
# =========================================================================


class TipoExperiencia(Enum):
    NO_IDENTIFICADO = "No Identificado"
    LABORAL = "Laboral"
    LABORAL_RELACIONADA = "Laboral Relacionada"
    PROFESIONAL = "Profesional"
    PROFESIONAL_RELACIONADA = "Profesional Relacionada"
    DOCENTE = "Docente"


HIERARQUIA_EXPERIENCIA: dict[TipoExperiencia, set[TipoExperiencia]] = {
    TipoExperiencia.PROFESIONAL_RELACIONADA: {
        TipoExperiencia.PROFESIONAL_RELACIONADA,
        TipoExperiencia.PROFESIONAL,
        TipoExperiencia.LABORAL_RELACIONADA,
        TipoExperiencia.LABORAL,
    },
    TipoExperiencia.PROFESIONAL: {
        TipoExperiencia.PROFESIONAL,
        TipoExperiencia.LABORAL,
    },
    TipoExperiencia.LABORAL_RELACIONADA: {
        TipoExperiencia.LABORAL_RELACIONADA,
        TipoExperiencia.LABORAL,
    },
    TipoExperiencia.DOCENTE: {
        TipoExperiencia.DOCENTE,
        TipoExperiencia.PROFESIONAL,
        TipoExperiencia.LABORAL,
    },
    TipoExperiencia.LABORAL: {
        TipoExperiencia.LABORAL,
    },
    TipoExperiencia.NO_IDENTIFICADO: {
        TipoExperiencia.NO_IDENTIFICADO,
    },
}


# =========================================================================
# Preprocesamiento — ports LITERALES del notebook
# =========================================================================


def _is_valid_data(data_str: str) -> bool:
    """notebook: _is_valid_data — no vacío y no 'nan'."""
    val = str(data_str).strip().lower()
    return bool(val and val != "nan")


def _unidecode(s: str) -> str:
    """Fallback si unidecode no está disponible (decomposición NFD)."""
    import unicodedata

    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


try:
    from unidecode import unidecode as _ud

    def _deaccent(s: str) -> str:
        return _ud(s)

except ImportError:
    def _deaccent(s: str) -> str:
        return _unidecode(s)


def normalizar_texto_func(txt: str) -> str:
    """notebook: normalizar_texto_func — lowercase + unaccent + strip. Nada más."""
    if not isinstance(txt, str):
        return ""
    return _deaccent(txt.strip().lower())


def remover_ordinales(line: str) -> str:
    """notebook: remover_ordinales — quita prefijos de viñetas/ordinales."""
    pattern = r"^\s*(?:[\[\(]?\d+[.\)\-\]]?|[\[\(]?[a-zA-Z][.\)\-\]]|[IVXLCDMivxlcdm]+[.\)\-\]]?|[•*\-\+])\s*"
    return re.sub(pattern, "", line).strip()


_GARBAGE_CONTENIDOS = [
    "demas funciones", "demas labores", "demas asignadas por",
    "demas que le sean asignadas", "y funciones similares",
    "otras funciones asignadas", "lo que le sea asignado por",
    "asignadas por el jefe inmediato", "asignadas por la ley",
    "funciones inherentes al cargo", "propio de su cargo", "propias del cargo",
    "actividades que le sean delegadas", "cumplir con las demas funciones",
]


def es_funcion_comodin(linea: str) -> bool:
    """notebook: es_funcion_comodin — comodines genéricos de funciones."""
    check = normalizar_texto_func(linea)
    return any(c in check for c in _GARBAGE_CONTENIDOS)


def es_ruido(linea: str, min_words: int = MIN_WORDS_PER_ITEM, es_funcion: bool = False) -> bool:
    """notebook: es_ruido — vacía, muy corta o comodín (si es función)."""
    stripped = linea.strip()
    if not stripped:
        return True
    palabras = remover_ordinales(stripped).split()
    if len(palabras) < min_words:
        return True
    if es_funcion and es_funcion_comodin(stripped):
        return True
    return False


def split_by_bullet_lines(text: str) -> list[str]:
    """notebook: split_by_bullet_lines — divide texto en ítems por viñetas/numeración."""
    bullet_pattern = re.compile(
        r"^\s*(?:[•\-*+]|\d+[.)]|[\[\(]?\d+[.\)\-\]]?|[a-zA-Z][.)]|[\[\(]?[a-zA-Z][.\)\-\]]?)\s*"
    )
    lines = str(text).splitlines()
    items: list[str] = []
    current: list[str] = []

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue
        is_bullet = bullet_pattern.match(line)
        if is_bullet:
            if current:
                items.append(" ".join(current).strip())
            clean_line = bullet_pattern.sub("", line).strip()
            current = [clean_line] if clean_line else []
        else:
            if current:
                current.append(line_stripped)
            elif items:
                items[-1] = f"{items[-1]} {line_stripped}"
            else:
                current.append(line_stripped)

    if current:
        items.append(" ".join(current).strip())

    # Fallback: si no hay viñetas, devolver líneas no vacías
    if not items and lines:
        items = [line.strip() for line in lines if line.strip()]

    return items


# --- Limpieza de educación (regexes exactos del notebook) ---

_EDU_PATTERNS = [
    r"^\s*t[íi]tulo\s+(?:profesional|de\s+formaci[óo]n)\s+(?:universitaria|tecnol[óo]gica|t[ée]cnica\s+profesional)\s*(?:en|en\s+la\s+disciplina\s+acad[ée]mica\s+de|en\s+el\s+[áa]rea\s+de|en\s+la\s+modalidad\s+de)?\s*\b",
    r"^\s*diploma\s+(?:de\s+bachiller|universitario|profesional)\s*(?:en)?\s*\b",
    r"^\s*(?:pregrado|posgrado|maestr[íi]a|especializaci[óo]n|doctorado)\s*(?:en\s+el\s+[áa]rea\s+de|en)?\s*\b",
    r"^\s*estudios\s+(?:profesionales?|universitarios?|t[ée]cnicos?|tecnol[óo]gicos?|de\s+posgrado|de\s+maestr[íi]a|de\s+especializaci[óo]n|de\s+doctorado)\s*(?:en)?\s*\b",
    r"^\s*formaci[óo]n\s+(?:profesional|universitaria|t[ée]nica|tecnol[óo]gica|de\s+posgrado|acad[ée]mica)\s*(?:en)?\s*\b",
    r"^\s*requiere\s+(?:t[íi]tulo|estudios?|formaci[óo]n)\s*(?:en)?\s*\b",
    r"^\s*(?:t[íi]tulo|certificado|diploma)\s+de\s+posgrado\s+(?:en\s+la\s+modalidad\s+de)?\s*(?:especializaci[óo]n|maestr[íi]a|doctorado)\s*(?:en)?\s*\b",
    r"\b(?:y|con|y\s+con)\s+(?:tarjeta|matr[íi]cula|licencia)\s+profesional\s+(?:vigente|activa|correspondiente|requerida|expedida).*",
    r"\b(?:tarjeta|matr[íi]cula|licencia)\s+profesional\b.*$",
    r"^\s*(?:tarjeta|matr[íi]cula)\s+profesional.*",
    r"\b(?:en\s+los\s+casos\s+(?:de\s+ley|reglamentados\s+por\s+la\s+ley))\b",
    r"^\s*n[úu]cleo\s+b[áa]sico\s+del\s+conocimiento\s*[:\s-]*\s*(?:en)?\s*",
    r"^\s*disciplina\s+acad[ée]mica\s*[:\s-]*\s*(?:en)?\s*",
    r"^\s*[áa]rea\s+del\s+conocimiento\s*[:\s-]*\s*(?:en)?\s*",
    r"^\s*nbc\s*[:\s-]*\s*",
    r"^\s*[a-z]\)\s*",
    r"^\s*\d+\.\s*",
]

_EDU_COMPILED = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in _EDU_PATTERNS]


def preprocesar_educacion(texto: str) -> str:
    """notebook: preprocesar_educacion — limpia frases introductorias de estudios."""
    if not isinstance(texto, str):
        return ""
    texto_proc = texto.lower()
    for pattern in _EDU_COMPILED:
        texto_proc = pattern.sub("", texto_proc).strip()
    texto_proc = re.sub(r"^\s*(nbc|n\.b\.c\.)\s*$", "", texto_proc, flags=re.IGNORECASE | re.MULTILINE)
    return texto_proc.strip()


def procesar_bloque(
    texto: str,
    aspecto: str,
    eliminar_duplicados: bool = ELIMINAR_DUPLICADOS,
    normalizar: bool = NORMALIZAR_TEXTO,
    lematizar: bool = LEMATIZAR,
    nlp_model=None,
    min_words: int = MIN_WORDS_PER_ITEM,
) -> list[str]:
    """
    notebook: procesar_bloque — extrae ítems significativos de un bloque de texto.

    aspecto ∈ {'Funciones', 'Educacion', 'Experiencia', 'Competencias Laborales',
               'Competencias Comportamentales'}
    """
    if not _is_valid_data(texto):
        return []

    texto_preprocesado = texto
    if aspecto == "Educacion":
        texto_preprocesado = preprocesar_educacion(texto)
        if not _is_valid_data(texto_preprocesado):
            return []

    items_crudos = split_by_bullet_lines(texto_preprocesado)
    items_procesados: list[str] = []
    vistos: set[str] = set()

    for item in items_crudos:
        if es_ruido(item, min_words, es_funcion=(aspecto == "Funciones")):
            continue

        item_for_processing = item
        if normalizar:
            item_for_processing = normalizar_texto_func(item_for_processing)

        if lematizar and nlp_model:
            # Lematización opcional con spaCy
            try:
                doc = nlp_model(item_for_processing)
                lemmas = [
                    tok.lemma_.lower()
                    for tok in doc
                    if not tok.is_punct and not tok.is_space and tok.lemma_.strip()
                ]
                item_for_processing = " ".join(lemmas)
            except Exception as e:
                logging.warning("Fallo lematizar: %s", e)

        if not item_for_processing or len(item_for_processing.split()) < min_words:
            continue

        clave = item_for_processing
        item_a_guardar = item
        if normalizar and not lematizar:
            item_a_guardar = normalizar_texto_func(item)
        elif lematizar:
            item_a_guardar = item_for_processing

        if eliminar_duplicados:
            if clave not in vistos:
                items_procesados.append(item_a_guardar)
                vistos.add(clave)
        else:
            items_procesados.append(item_a_guardar)

    return items_procesados


# --- Experiencia con jerarquía (ports literales) ---


def extraer_tipo_y_texto_experiencia(texto: str) -> tuple[TipoExperiencia, str]:
    """notebook: extraer_tipo_y_texto_experiencia — tipo + texto limpio sin el marcador."""
    if not isinstance(texto, str):
        return TipoExperiencia.NO_IDENTIFICADO, ""

    texto_norm = normalizar_texto_func(texto)
    texto_limpio = texto

    patterns = [
        (TipoExperiencia.PROFESIONAL_RELACIONADA, r"experiencia\s+profesional\s+relacionada"),
        (TipoExperiencia.LABORAL_RELACIONADA, r"experiencia\s+laboral\s+relacionada"),
        (TipoExperiencia.PROFESIONAL, r"experiencia\s+profesional"),
        (TipoExperiencia.DOCENTE, r"experiencia\s+docente"),
        (TipoExperiencia.LABORAL, r"experiencia\s+laboral"),
    ]

    for tipo, pat in patterns:
        if re.search(pat, texto_norm):
            texto_limpio = re.sub(pat, "", texto, flags=re.IGNORECASE).strip()
            return tipo, texto_limpio

    if "experiencia" in texto_norm:
        return TipoExperiencia.LABORAL, texto
    return TipoExperiencia.NO_IDENTIFICADO, texto


def verificar_jerarquia_experiencia(
    tipo_base: TipoExperiencia,
    tipo_destino_requerido: TipoExperiencia,
) -> tuple[bool, str]:
    """notebook: verificar_jerarquia_experiencia."""
    if (
        tipo_destino_requerido == TipoExperiencia.NO_IDENTIFICADO
        or tipo_base == TipoExperiencia.NO_IDENTIFICADO
    ):
        return True, "No se identificó tipo de experiencia específico; se omite verificación."

    aceptables = HIERARQUIA_EXPERIENCIA.get(tipo_base, set())
    if tipo_destino_requerido in aceptables:
        return True, (
            f"Jerarquía Válida: '{tipo_base.value}' del Base "
            f"satisface '{tipo_destino_requerido.value}' del Destino."
        )
    return False, (
        f"Jerarquía Inválida: '{tipo_base.value}' del Base "
        f"NO satisface '{tipo_destino_requerido.value}' del Destino."
    )


# =========================================================================
# Comparación Nivel y Salario (ports literales)
# =========================================================================


def comparar_niveles(nivel_base: str, nivel_destino: str) -> tuple[bool, str]:
    """notebook: comparar_niveles — idéntico después de normalizar."""
    n1 = normalizar_texto_func(str(nivel_base or "")).strip()
    n2 = normalizar_texto_func(str(nivel_destino or "")).strip()
    if not n1 or not n2:
        return False, f"Niveles no especificados: Base='{nivel_base}', Destino='{nivel_destino}'. No Pasa."
    if n1 == n2:
        return True, f"Ambos son Nivel '{nivel_base}'. Pasa."
    return False, f"Niveles diferentes: Base='{nivel_base}', Destino='{nivel_destino}'. No Pasa."


_ENTIDADES_NACIONAL = [
    "ministerio", "departamento administrativo", "superintendencia",
    "unidad administrativa especial", "establecimiento publico",
    "corporacion autonoma regional y de desarrollo sostenible",
    "empresa social del estado (ese)",
    "empresa industrial y comercial del estado (eice)",
    "sociedad de economia mixta (regimen eice)",
    "otra institucion publica ejecutiva nacional",
    "entidad en liquidacion nacional",
]


def comparar_salarios(
    s1: float,
    s2: float,
    g1: int,
    g2: int,
    orden1: str = "",
    nat1: str = "",
    orden2: str = "",
    nat2: str = "",
) -> tuple[bool, str]:
    """notebook: comparar_salarios — exige MISMO GRADO exacto + salarios > 0."""
    try:
        s1 = float(s1)
        s2 = float(s2)
        g1 = int(g1) if pd.notna(g1) else -1
        g2 = int(g2) if pd.notna(g2) else -1
    except (ValueError, TypeError):
        return False, "Salarios o grados con formato inválido. No Pasa."

    if s1 <= 0 or s2 <= 0:
        return False, f"Salarios inválidos (Base: {s1:,.0f}, Destino: {s2:,.0f}). Deben ser > 0. No Pasa."

    # VALIDACIÓN CRÍTICA del notebook: grados exactos
    if g1 != -1 and g2 != -1 and g1 != g2:
        return False, (
            f"Grados diferentes: Base(G{g1}) ≠ Destino(G{g2}). "
            f"Se requiere MISMO GRADO exacto. No Pasa."
        )

    diff = abs(s1 - s2) / s1 if s1 else 1.0
    if diff > SALARY_DIFF_PERCENTAGE_THRESHOLD:
        return False, (
            f"Diferencia salarial {diff:.1%} > {SALARY_DIFF_PERCENTAGE_THRESHOLD:.0%}: "
            f"{s1:,.0f} vs {s2:,.0f}. No Pasa."
        )

    return True, f"Mismo grado G{g1} y salarios equivalentes ({diff:.1%} diferencia)."


# =========================================================================
# SBERT — carga del modelo y cálculo de similitud
# =========================================================================


def cargar_modelo(nombre: str = SBERT_MODEL_NAME):
    """Carga el modelo SBERT en CPU/GPU. Cacheado por proceso."""
    return _cargar_modelo_cache(nombre)


@lru_cache(maxsize=2)
def _cargar_modelo_cache(nombre: str):
    from sentence_transformers import SentenceTransformer
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logging.info("Cargando SBERT '%s' en %s…", nombre, device.upper())
    return SentenceTransformer(nombre, device=device)


def _cos_sim_matriz(emb_1: np.ndarray, emb_2: np.ndarray) -> np.ndarray:
    """Coseno entre dos matrices. Asume embeddings no necesariamente normalizados."""
    def _norm(m):
        denom = np.linalg.norm(m, axis=1, keepdims=True)
        denom[denom == 0] = 1.0
        return m / denom

    n1 = _norm(emb_1.astype(np.float32))
    n2 = _norm(emb_2.astype(np.float32))
    matriz = n1 @ n2.T
    return np.clip(matriz, 0.0, 1.0)


def _jaccard_binario(items_1: list[str], items_2: list[str]) -> np.ndarray:
    """Jaccard sobre tokens — se usa sólo si usar_jaccard=True (el default del notebook es False)."""
    num_1 = len(items_1)
    num_2 = len(items_2)
    matriz = np.zeros((num_1, num_2), dtype=np.float32)
    for i, a in enumerate(items_1):
        sa = set(a.split())
        for j, b in enumerate(items_2):
            sb = set(b.split())
            if not sa and not sb:
                matriz[i, j] = 1.0
            elif sa and sb:
                inter = len(sa & sb)
                uni = len(sa | sb)
                matriz[i, j] = inter / uni if uni else 0.0
    return matriz


def calcular_matriz_similitud_combinada(
    items_1: list[str],
    items_2: list[str],
    model,
    embeddings_cache: Optional[dict[str, np.ndarray]] = None,
    usar_jaccard: bool = USAR_JACCARD,
    peso_coseno: float = PESO_COSENO,
    peso_jaccard: float = PESO_JACCARD,
) -> np.ndarray:
    """
    notebook: calcular_matriz_similitud_combinada.

    Encoding inteligente: si `embeddings_cache` se pasa, reutiliza embeddings
    ya computados por texto único — evita recomputar lo mismo N veces en modo masivo.
    """
    num_1 = len(items_1)
    num_2 = len(items_2)
    if num_1 == 0 or num_2 == 0 or model is None:
        return np.zeros((num_1, num_2))

    if usar_jaccard and (peso_coseno + peso_jaccard > 1e-9):
        suma = peso_coseno + peso_jaccard
        w_cos = peso_coseno / suma
        w_jacc = peso_jaccard / suma
    else:
        w_cos = 1.0
        w_jacc = 0.0
        usar_jaccard = False

    emb_1 = _encode_con_cache(items_1, model, embeddings_cache)
    emb_2 = _encode_con_cache(items_2, model, embeddings_cache)

    if emb_1.size == 0 or emb_2.size == 0:
        return np.zeros((num_1, num_2))

    matriz_cos = _cos_sim_matriz(emb_1, emb_2)

    if usar_jaccard and w_jacc > 1e-9:
        matriz_jac = _jaccard_binario(items_1, items_2)
        return (matriz_cos * w_cos) + (matriz_jac * w_jacc)
    return matriz_cos


def _encode_con_cache(
    items: list[str],
    model,
    cache: Optional[dict[str, np.ndarray]],
) -> np.ndarray:
    """Encode reusando embeddings cacheados; los ítems nuevos se encoden en batch."""
    if not items:
        return np.zeros((0, 0), dtype=np.float32)

    if cache is None:
        return model.encode(items, convert_to_numpy=True, show_progress_bar=False)

    faltantes = [it for it in items if it not in cache]
    if faltantes:
        nuevos = model.encode(faltantes, convert_to_numpy=True, show_progress_bar=False)
        for text, emb in zip(faltantes, nuevos):
            cache[text] = emb

    return np.stack([cache[it] for it in items])


def calcular_metricas_agregadas(matriz: np.ndarray) -> dict[str, float]:
    """notebook: calcular_metricas_agregadas — devuelve cobertura_prom_max_1 + _2 + promedio."""
    metricas = {"cobertura_prom_max_1": 0.0, "cobertura_prom_max_2": 0.0, "sim_promedio_total": 0.0}
    if matriz.ndim == 2 and matriz.size > 0:
        try:
            max_filas = np.max(matriz, axis=1)
            if max_filas.size > 0:
                metricas["cobertura_prom_max_1"] = float(np.mean(max_filas))
            max_cols = np.max(matriz, axis=0)
            if max_cols.size > 0:
                metricas["cobertura_prom_max_2"] = float(np.mean(max_cols))
            metricas["sim_promedio_total"] = float(np.mean(matriz))
        except Exception as e:
            logging.error("Error en métricas agregadas: %s", e)
    return metricas


# =========================================================================
# Análisis de un par completo
# =========================================================================


@dataclass
class AspectoResult:
    items1: list[str] = field(default_factory=list)
    items2: list[str] = field(default_factory=list)
    cobertura: float = 0.0  # cobertura_prom_max_1
    error: Optional[str] = None
    jerarquia_msg: Optional[str] = None


@dataclass
class AspectosResult:
    """Resultado de analizar un par (base, lista) sobre los 5 aspectos + gating."""

    funciones: AspectoResult = field(default_factory=AspectoResult)
    estudio: AspectoResult = field(default_factory=AspectoResult)
    comp_lab: AspectoResult = field(default_factory=AspectoResult)
    comp_comp: AspectoResult = field(default_factory=AspectoResult)
    experiencia: AspectoResult = field(default_factory=AspectoResult)

    tipo_exp_base: TipoExperiencia = TipoExperiencia.NO_IDENTIFICADO
    tipo_exp_destino: TipoExperiencia = TipoExperiencia.NO_IDENTIFICADO

    nivel_pasa: bool = False
    nivel_msg: str = ""
    salario_pasa: bool = False
    salario_msg: str = ""

    modelo_usado: str = SBERT_MODEL_NAME


def _get(row: pd.Series, col: str, default: str = "") -> str:
    if col not in row.index:
        return default
    val = row[col]
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    return str(val)


def _calc_aspecto(
    texto_base: str,
    texto_destino: str,
    aspecto: str,
    model,
    embeddings_cache: Optional[dict[str, np.ndarray]],
    nlp_model=None,
) -> AspectoResult:
    """Procesa y calcula cobertura de un aspecto genérico (no experiencia)."""
    items1 = procesar_bloque(texto_base, aspecto, nlp_model=nlp_model)
    items2 = procesar_bloque(texto_destino, aspecto, nlp_model=nlp_model)

    res = AspectoResult(items1=items1, items2=items2)

    if not items1 and not items2:
        res.cobertura = 1.0  # notebook: ambos vacíos → pasa trivialmente (igual que eval_crit)
        return res
    if not items1 or not items2:
        res.error = f"Datos insuficientes en '{aspecto}'."
        return res

    matriz = calcular_matriz_similitud_combinada(items1, items2, model, embeddings_cache)
    metricas = calcular_metricas_agregadas(matriz)
    res.cobertura = metricas.get("cobertura_prom_max_1", 0.0)
    return res


def _calc_experiencia(
    texto_base: str,
    texto_destino: str,
    model,
    embeddings_cache: Optional[dict[str, np.ndarray]],
    nlp_model=None,
) -> tuple[AspectoResult, TipoExperiencia, TipoExperiencia]:
    """notebook: calcular_similitud_experiencia_con_jerarquia."""
    tipo_base, texto_limpio_base = extraer_tipo_y_texto_experiencia(texto_base)
    tipo_destino, texto_limpio_destino = extraer_tipo_y_texto_experiencia(texto_destino)

    jerarquia_ok, msg = verificar_jerarquia_experiencia(tipo_base, tipo_destino)
    res = AspectoResult(jerarquia_msg=msg)

    if not jerarquia_ok:
        res.error = "Jerarquía de experiencia no es compatible."
        return res, tipo_base, tipo_destino

    # Si la jerarquía pasa, comparar el texto limpio semánticamente
    sim = _calc_aspecto(texto_limpio_base, texto_limpio_destino, "Experiencia", model, embeddings_cache, nlp_model)
    res.items1 = sim.items1
    res.items2 = sim.items2
    res.cobertura = sim.cobertura
    if sim.error:
        res.error = sim.error
    return res, tipo_base, tipo_destino


def analizar_par(
    base: pd.Series,
    destino: pd.Series,
    model,
    embeddings_cache: Optional[dict[str, np.ndarray]] = None,
    nlp_model=None,
) -> AspectosResult:
    """
    Ejecuta el análisis semántico completo de un par (base, destino) replicando
    EXACTAMENTE el flujo del notebook para un solo destino dentro de on_analizar_click.
    """
    result = AspectosResult()

    # Gating — nivel y salario
    result.nivel_pasa, result.nivel_msg = comparar_niveles(
        _get(base, "Nivel Jerárquico"),
        _get(destino, "Nivel Jerárquico"),
    )
    result.salario_pasa, result.salario_msg = comparar_salarios(
        _get(base, "Salario", "0") or "0",
        _get(destino, "Salario", "0") or "0",
        _get(base, "Grado", "-1") or "-1",
        _get(destino, "Grado", "-1") or "-1",
        _get(base, "Orden"),
        _get(base, "Naturaleza Jurídica"),
        _get(destino, "Orden"),
        _get(destino, "Naturaleza Jurídica"),
    )

    # 5 aspectos semánticos
    result.funciones = _calc_aspecto(
        _get(base, "Funciones"), _get(destino, "Funciones"),
        "Funciones", model, embeddings_cache, nlp_model,
    )
    result.estudio = _calc_aspecto(
        _get(base, "Requisitos Estudio"), _get(destino, "Requisitos Estudio"),
        "Educacion", model, embeddings_cache, nlp_model,
    )
    result.comp_lab = _calc_aspecto(
        _get(base, "Competencias Laborales"), _get(destino, "Competencias Laborales"),
        "Competencias Laborales", model, embeddings_cache, nlp_model,
    )
    result.comp_comp = _calc_aspecto(
        _get(base, "Competencias Comportamentales"), _get(destino, "Competencias Comportamentales"),
        "Competencias Comportamentales", model, embeddings_cache, nlp_model,
    )
    result.experiencia, result.tipo_exp_base, result.tipo_exp_destino = _calc_experiencia(
        _get(base, "Requisitos Experiencia"), _get(destino, "Requisitos Experiencia"),
        model, embeddings_cache, nlp_model,
    )

    return result


# =========================================================================
# Batching masivo: pre-encode de todos los textos únicos antes de iterar
# =========================================================================


def pre_cachear_embeddings(grupos, model) -> dict[str, np.ndarray]:
    """
    Antes del loop masivo, recolecta TODOS los ítems únicos de TODOS los grupos
    (después del preprocesamiento) y los encoda en un solo batch. Cachea los
    embeddings en un dict {texto: vector}.

    Resultado típico: 500 pares × 5 aspectos = 2500 bloques, pero con ~200-400
    ítems únicos después de deduplicar → 10x menos encoding calls.
    """
    cache: dict[str, np.ndarray] = {}
    textos_unicos: set[str] = set()

    aspectos_cols = {
        "Funciones": "Funciones",
        "Educacion": "Requisitos Estudio",
        "Competencias Laborales": "Competencias Laborales",
        "Competencias Comportamentales": "Competencias Comportamentales",
    }

    def _recolectar(row: pd.Series):
        for aspecto, col in aspectos_cols.items():
            items = procesar_bloque(_get(row, col), aspecto)
            for it in items:
                textos_unicos.add(it)
        # Experiencia (con limpieza de tipo)
        _, exp_texto = extraer_tipo_y_texto_experiencia(_get(row, "Requisitos Experiencia"))
        for it in procesar_bloque(exp_texto, "Experiencia"):
            textos_unicos.add(it)

    for g in grupos:
        _recolectar(g.base)
        for _, lista_row in g.listas.iterrows():
            _recolectar(lista_row)

    textos_lista = sorted(textos_unicos)
    if not textos_lista:
        return cache

    logging.info("Pre-encoding %d textos únicos en batch…", len(textos_lista))
    embs = model.encode(textos_lista, convert_to_numpy=True, show_progress_bar=False, batch_size=32)
    for text, emb in zip(textos_lista, embs):
        cache[text] = emb

    return cache
