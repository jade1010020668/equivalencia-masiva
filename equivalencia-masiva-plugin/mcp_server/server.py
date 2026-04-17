"""
MCP server — Equivalencia Masiva (Despacho III EARM, CNSC).

Expone las funciones del módulo `core/` del proyecto Equivalencia Masiva como
tools MCP invocables desde cualquier Claude Code con el plugin instalado.

Diseño:
  - El servidor está DENTRO del plugin pero importa `core.*` del proyecto padre
    (dos niveles arriba). `${CLAUDE_PLUGIN_ROOT}/..` se añade al PYTHONPATH vía
    `.mcp.json` para que Python encuentre los módulos.
  - Todas las tools son stateless: reciben un path al Excel, cargan, procesan,
    devuelven resultado. Sin base de datos ni sesiones.
  - Los embeddings SBERT se cachean dentro del proceso MCP (LRU) — si Claude
    invoca varias tools seguidas sobre el mismo Excel, sólo se encodea una vez.

Uso desde Claude Code (después de instalar el plugin):

    Usuario: "Analízame C:/data/opec_abril.xlsx"
    Claude: [invoca mcp__equivalencia-masiva-core__analizar_masivo]

Tools disponibles:
  - agrupar_excel          → lista de grupos (base 4.0 + listas candidatas)
  - analizar_par           → scores + veredicto para un par específico
  - analizar_masivo        → loop completo sobre todos los pares del Excel
  - generar_plantilla      → Excel plantilla vacío
  - generar_reporte_excel  → Excel consolidado del análisis
  - generar_reporte_pdf    → PDF detallado del análisis
  - validar_columnas       → chequeo rápido de columnas requeridas
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Asegurar que `core/` y `config.py` del proyecto padre sean importables.
# El plugin vive en <proyecto>/equivalencia-masiva-plugin/mcp_server/
# y los módulos core están en <proyecto>/core/.
# ---------------------------------------------------------------------------
_THIS_FILE = Path(__file__).resolve()
_PLUGIN_ROOT = _THIS_FILE.parent.parent          # equivalencia-masiva-plugin/
_PROJECT_ROOT = _PLUGIN_ROOT.parent                # <proyecto>/
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Logging al stderr (stdout está reservado para JSON-RPC del MCP)
logging.basicConfig(
    level=os.environ.get("EQUIVALENCIA_MASIVA_LOG_LEVEL", "INFO"),
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("equivalencia-masiva-mcp")

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    log.error(
        "FastMCP no está instalado. Corre: pip install 'mcp[cli]'"
        " dentro del mismo Python que arranca el servidor."
    )
    raise

# Los módulos del proyecto — importación tardía para dar mensaje claro si fallan.
try:
    import pandas as pd
    from config import REQUIRED_COLUMNS
    from core import decision as decision_mod
    from core import grouping as grouping_mod
    from core import pdf_report as pdf_mod
    from core import report as report_mod
    from core import semantic as semantic_mod
    from core import template as template_mod
except Exception as exc:  # pragma: no cover
    log.error("Fallo al importar módulos del proyecto padre: %s", exc)
    raise


# ---------------------------------------------------------------------------
# Servidor MCP
# ---------------------------------------------------------------------------
mcp = FastMCP(
    name="equivalencia-masiva-core",
    instructions=(
        "MCP server del Despacho III EARM (CNSC). Expone las funciones de "
        "análisis masivo de equivalencia de empleos. Cuando el usuario "
        "mencione OPEC, listas de elegibles, o equivalencia de empleos, "
        "usa estas tools para ejecutar el pipeline sin necesidad de abrir "
        "la app Streamlit."
    ),
)


# ---------------------------------------------------------------------------
# Cache del modelo SBERT (se carga una sola vez por proceso)
# ---------------------------------------------------------------------------
_model_cache: dict[str, object] = {}


def _get_model(modelo_nombre: Optional[str] = None):
    """Carga perezosa del modelo SBERT. Primera llamada descarga el modelo."""
    nombre = modelo_nombre or "hiiamsid/sentence_similarity_spanish_es"
    if nombre not in _model_cache:
        log.info("Cargando modelo SBERT '%s' (primera vez puede tardar 1-2 min)…", nombre)
        _model_cache[nombre] = semantic_mod.cargar_modelo(nombre)
    return _model_cache[nombre]


# ===========================================================================
# Tool: validar_columnas
# ===========================================================================
@mcp.tool()
def validar_columnas(ruta_excel: str) -> dict:
    """
    Valida que un Excel tenga las 15 columnas requeridas del pipeline CNSC.

    Args:
        ruta_excel: Ruta absoluta al archivo .xlsx (o .xls).

    Returns:
        dict con:
          - ok (bool): True si todas las columnas están presentes.
          - faltantes (list[str]): columnas requeridas que faltan.
          - filas_totales (int): cantidad de filas en el Excel.
          - ruta (str): la misma ruta de entrada (para trazabilidad).
    """
    path = Path(ruta_excel)
    if not path.exists():
        return {"ok": False, "error": f"Archivo no encontrado: {ruta_excel}"}
    try:
        df = pd.read_excel(path)
    except Exception as exc:
        return {"ok": False, "error": f"Error leyendo Excel: {exc}"}

    faltantes = grouping_mod.validar_columnas(df)
    return {
        "ok": not faltantes,
        "faltantes": faltantes,
        "filas_totales": len(df),
        "columnas_requeridas": list(REQUIRED_COLUMNS),
        "ruta": str(path.resolve()),
    }


# ===========================================================================
# Tool: agrupar_excel
# ===========================================================================
@mcp.tool()
def agrupar_excel(ruta_excel: str) -> dict:
    """
    Agrupa cada empleo base 4.0 con sus listas candidatas del mismo grado/nivel/entidad.

    Replica exactamente el agrupamiento de la app Criterio Base (React) portado
    a Python en `core/grouping.py`.

    Args:
        ruta_excel: Ruta absoluta al archivo .xlsx.

    Returns:
        dict con:
          - ok (bool)
          - total_grupos (int)
          - total_pares (int): suma de listas candidatas en todos los grupos.
          - grupos (list[dict]): uno por cada empleo base 4.0.
    """
    path = Path(ruta_excel)
    if not path.exists():
        return {"ok": False, "error": f"Archivo no encontrado: {ruta_excel}"}
    try:
        df = pd.read_excel(path)
    except Exception as exc:
        return {"ok": False, "error": f"Error leyendo Excel: {exc}"}

    faltantes = grouping_mod.validar_columnas(df)
    if faltantes:
        return {"ok": False, "error": "Faltan columnas requeridas", "faltantes": faltantes}

    grupos = grouping_mod.agrupar_dataframe(df)
    grupos_out = []
    for g in grupos:
        grupos_out.append({
            "nombre": g.nombre,
            "entidad": g.entidad,
            "nivel": g.nivel,
            "grado": g.grado,
            "opec_base": str(g.base.get("No. OPEC", "")),
            "denominacion_base": str(g.base.get("Denominación", "")),
            "listas_count": len(g.listas),
            "listas_opec": [str(o) for o in g.listas["No. OPEC"].tolist()],
            "is_lonely": g.is_lonely,
        })

    return {
        "ok": True,
        "total_grupos": len(grupos),
        "total_pares": sum(len(g.listas) for g in grupos),
        "bases_huerfanas": sum(1 for g in grupos if g.is_lonely),
        "grupos": grupos_out,
    }


# ===========================================================================
# Tool: analizar_par
# ===========================================================================
@mcp.tool()
def analizar_par(
    ruta_excel: str,
    opec_base: str,
    opec_lista: str,
    umbral_funciones: float = 0.60,
    umbral_estudio: float = 0.70,
    umbral_comp: float = 0.65,
    incluir_requisitos: bool = True,
) -> dict:
    """
    Analiza semánticamente UN par (base 4.0, lista candidata) específico.

    Útil cuando el usuario quiere revisar a fondo un caso particular,
    por ejemplo: "analiza el par OPEC 221860 vs 152423 del Excel X".

    Args:
        ruta_excel: Ruta absoluta al Excel.
        opec_base: No. OPEC del empleo base (modalidad 4.0).
        opec_lista: No. OPEC de la lista candidata (modalidad LISTAS).
        umbral_funciones: Cobertura mínima para funciones (default notebook: 0.60).
        umbral_estudio: Cobertura mínima para requisitos estudio (default: 0.70).
        umbral_comp: Cobertura mínima para competencias (default: 0.65).
        incluir_requisitos: Si True, estudio y competencias gatean la decisión.

    Returns:
        dict con scores SBERT, veredicto, razones, gating (nivel/salario), jerarquía exp.
    """
    path = Path(ruta_excel)
    if not path.exists():
        return {"ok": False, "error": f"Archivo no encontrado: {ruta_excel}"}
    df = pd.read_excel(path)
    faltantes = grouping_mod.validar_columnas(df)
    if faltantes:
        return {"ok": False, "error": "Faltan columnas", "faltantes": faltantes}

    # Normalizar OPEC (puede venir como float 428030.0 → "428030")
    def _opec_str(v) -> str:
        try:
            return str(int(float(str(v))))
        except (ValueError, TypeError):
            return str(v).strip()

    df["__opec_norm__"] = df["No. OPEC"].apply(_opec_str)
    df["__mod_clean__"] = df["modalidad"].apply(grouping_mod._modalidad_clean)

    base_rows = df[(df["__opec_norm__"] == _opec_str(opec_base))
                   & (df["__mod_clean__"] == "4.0")]
    lista_rows = df[(df["__opec_norm__"] == _opec_str(opec_lista))
                    & (df["__mod_clean__"] == "LISTAS")]

    if base_rows.empty:
        return {"ok": False, "error": f"OPEC base '{opec_base}' con modalidad 4.0 no encontrada"}
    if lista_rows.empty:
        return {"ok": False, "error": f"OPEC lista '{opec_lista}' con modalidad LISTAS no encontrada"}

    base = base_rows.iloc[0]
    lista = lista_rows.iloc[0]

    model = _get_model()
    aspectos = semantic_mod.analizar_par(base, lista, model)
    dec = decision_mod.decidir(
        aspectos,
        umbral_funciones=umbral_funciones,
        umbral_estudio=umbral_estudio,
        umbral_comp=umbral_comp,
        incluir_requisitos=incluir_requisitos,
    )

    return {
        "ok": True,
        "opec_base": opec_base,
        "opec_lista": opec_lista,
        "veredicto": dec.clasificacion,
        "es_equivalente": dec.es_equivalente,
        "score_ponderado": round(dec.score, 4),
        "razones_no_eq": dec.razones,
        "scores_sbert": {
            "funciones": round(aspectos.funciones.cobertura, 4),
            "estudio": round(aspectos.estudio.cobertura, 4),
            "comp_laborales": round(aspectos.comp_lab.cobertura, 4),
            "comp_comportamentales": round(aspectos.comp_comp.cobertura, 4),
            "experiencia": round(aspectos.experiencia.cobertura, 4),
        },
        "gating": {
            "nivel_pasa": aspectos.nivel_pasa,
            "nivel_msg": aspectos.nivel_msg,
            "salario_pasa": aspectos.salario_pasa,
            "salario_msg": aspectos.salario_msg,
        },
        "experiencia": {
            "tipo_base": aspectos.tipo_exp_base.value,
            "tipo_destino": aspectos.tipo_exp_destino.value,
            "jerarquia_msg": aspectos.experiencia.jerarquia_msg,
        },
        "umbrales_usados": {
            "funciones": umbral_funciones,
            "estudio": umbral_estudio,
            "comp": umbral_comp,
            "incluir_requisitos": incluir_requisitos,
        },
    }


# ===========================================================================
# Tool: analizar_masivo
# ===========================================================================
@mcp.tool()
def analizar_masivo(
    ruta_excel: str,
    umbral_funciones: float = 0.60,
    umbral_estudio: float = 0.70,
    umbral_comp: float = 0.65,
    incluir_requisitos: bool = True,
    limite_pares: Optional[int] = None,
) -> dict:
    """
    Corre el pipeline completo sobre TODO el Excel.

    Por cada par (base 4.0, lista) calcula SBERT + decisión AND, acumula filas,
    devuelve resumen + detalle.

    Args:
        ruta_excel: Ruta absoluta al Excel.
        umbral_funciones, umbral_estudio, umbral_comp: umbrales SBERT.
        incluir_requisitos: Si True, estudio+competencias gatean.
        limite_pares: Si se especifica, sólo procesa los primeros N pares
            (útil para smoke tests rápidos).

    Returns:
        dict con totales por clasificación, lista de pares analizados,
        ID único de la corrida (para generar reportes después).
    """
    path = Path(ruta_excel)
    if not path.exists():
        return {"ok": False, "error": f"Archivo no encontrado: {ruta_excel}"}
    df = pd.read_excel(path)
    faltantes = grouping_mod.validar_columnas(df)
    if faltantes:
        return {"ok": False, "error": "Faltan columnas", "faltantes": faltantes}

    grupos = grouping_mod.agrupar_dataframe(df)
    if not grupos:
        return {"ok": False, "error": "No se generaron grupos (¿falta modalidad 4.0?)"}

    model = _get_model()
    emb_cache = semantic_mod.pre_cachear_embeddings(grupos, model)

    filas = []
    pares_procesados = 0

    for grupo in grupos:
        if grupo.listas.empty:
            continue
        for _, lista_row in grupo.listas.iterrows():
            if limite_pares is not None and pares_procesados >= limite_pares:
                break
            try:
                aspectos = semantic_mod.analizar_par(grupo.base, lista_row, model, emb_cache)
                dec = decision_mod.decidir(
                    aspectos,
                    umbral_funciones=umbral_funciones,
                    umbral_estudio=umbral_estudio,
                    umbral_comp=umbral_comp,
                    incluir_requisitos=incluir_requisitos,
                )
                filas.append(report_mod.construir_fila(
                    grupo_nombre=grupo.nombre,
                    entidad=grupo.entidad,
                    base=grupo.base,
                    lista=lista_row,
                    aspectos=aspectos,
                    decision=dec,
                ))
                pares_procesados += 1
            except Exception as exc:  # pragma: no cover
                log.warning("Error en par %s-%s: %s",
                            grupo.base.get("No. OPEC"), lista_row.get("No. OPEC"), exc)
        if limite_pares is not None and pares_procesados >= limite_pares:
            break

    # Cachear las filas en disco para poder generar reportes después sin
    # re-ejecutar todo el análisis. Usamos un archivo por corrida.
    import hashlib, json, tempfile
    run_id = hashlib.sha1(
        f"{path.resolve()}-{umbral_funciones}-{umbral_estudio}-{umbral_comp}-{incluir_requisitos}".encode()
    ).hexdigest()[:12]
    cache_path = Path(tempfile.gettempdir()) / f"equivalencia_masiva_{run_id}.json"
    try:
        cache_path.write_text(
            json.dumps([asdict(f) for f in filas], default=str, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as exc:
        log.warning("No pude cachear filas: %s", exc)

    # Resumen
    from collections import Counter
    counter = Counter(f.decision_final for f in filas)

    return {
        "ok": True,
        "run_id": run_id,
        "cache_path": str(cache_path),
        "total_pares_analizados": len(filas),
        "total_grupos": len(grupos),
        "totales": {
            "EQUIVALENTE": counter.get("EQUIVALENTE", 0),
            "NO_EQUIVALENTE": counter.get("NO_EQUIVALENTE", 0),
        },
        "pares": [
            {
                "grupo": f.grupo,
                "opec_base": f.opec_base,
                "opec_lista": f.opec_lista,
                "denom_lista": f.denom_lista[:80],
                "veredicto": f.decision_final,
                "score": round(f.score_ponderado, 4),
                "sbert_funciones": round(f.sbert_funciones, 4),
                "sbert_estudio": round(f.sbert_estudio, 4),
                "razon_principal": (f.razones_no_eq.split(" | ")[0] if f.razones_no_eq else ""),
            }
            for f in filas
        ],
    }


# ===========================================================================
# Tool: generar_plantilla
# ===========================================================================
@mcp.tool()
def generar_plantilla(ruta_salida: Optional[str] = None) -> dict:
    """
    Genera un Excel plantilla con las 15 columnas requeridas, tooltips y ejemplos.

    Args:
        ruta_salida: Ruta donde guardar. Por defecto: `./plantilla_equivalencia_masiva.xlsx`

    Returns:
        dict con path del archivo generado y su tamaño.
    """
    if not ruta_salida:
        ruta_salida = str(Path.cwd() / "plantilla_equivalencia_masiva.xlsx")

    path = Path(ruta_salida).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        data = template_mod.generar_plantilla_excel()
        path.write_bytes(data)
    except Exception as exc:
        return {"ok": False, "error": f"Error generando plantilla: {exc}"}

    return {
        "ok": True,
        "ruta": str(path),
        "tamanio_bytes": len(data),
        "tamanio_kb": round(len(data) / 1024, 1),
        "contenido": "15 columnas + 3 filas de ejemplo + pestaña Instrucciones",
    }


# ===========================================================================
# Tools: generar_reporte_excel / generar_reporte_pdf
# ===========================================================================
def _cargar_filas_desde_cache(run_id: str) -> list:
    """Lee las filas persistidas por `analizar_masivo` usando el run_id."""
    import json, tempfile
    cache_path = Path(tempfile.gettempdir()) / f"equivalencia_masiva_{run_id}.json"
    if not cache_path.exists():
        return []
    data = json.loads(cache_path.read_text(encoding="utf-8"))

    # Reconstruir los dataclasses FilaReporte
    from core.report import FilaReporte
    filas = []
    for d in data:
        # Ensure types match
        d["salario_base"] = float(d.get("salario_base", 0) or 0)
        d["salario_lista"] = float(d.get("salario_lista", 0) or 0)
        filas.append(FilaReporte(**d))
    return filas


@mcp.tool()
def generar_reporte_excel(run_id: str, ruta_salida: Optional[str] = None) -> dict:
    """
    Genera el Excel consolidado a partir de un `run_id` devuelto por `analizar_masivo`.

    Args:
        run_id: ID devuelto por la tool `analizar_masivo`.
        ruta_salida: Ruta destino. Por defecto: `./Equivalencia_Masiva_<run_id>.xlsx`

    Returns:
        dict con path del archivo generado.
    """
    filas = _cargar_filas_desde_cache(run_id)
    if not filas:
        return {"ok": False, "error": f"No hay datos cacheados para run_id={run_id}. ¿Corriste analizar_masivo antes?"}

    if not ruta_salida:
        ruta_salida = str(Path.cwd() / f"Equivalencia_Masiva_{run_id}.xlsx")

    path = Path(ruta_salida).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        data = report_mod.exportar_excel(filas, f"run_{run_id}")
        path.write_bytes(data)
    except Exception as exc:
        return {"ok": False, "error": f"Error generando Excel: {exc}"}

    return {
        "ok": True,
        "ruta": str(path),
        "tamanio_kb": round(len(data) / 1024, 1),
        "filas": len(filas),
    }


@mcp.tool()
def generar_reporte_pdf(run_id: str, ruta_salida: Optional[str] = None) -> dict:
    """
    Genera el PDF detallado (portada + resumen + detalle por grupo + par por par).

    Args:
        run_id: ID devuelto por `analizar_masivo`.
        ruta_salida: Path destino. Por defecto: `./Equivalencia_Masiva_<run_id>.pdf`

    Returns:
        dict con path del PDF generado.
    """
    filas = _cargar_filas_desde_cache(run_id)
    if not filas:
        return {"ok": False, "error": f"No hay datos cacheados para run_id={run_id}. ¿Corriste analizar_masivo antes?"}

    if not ruta_salida:
        ruta_salida = str(Path.cwd() / f"Equivalencia_Masiva_{run_id}.pdf")

    path = Path(ruta_salida).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        data = pdf_mod.generar_pdf(filas, f"run_{run_id}")
        path.write_bytes(data)
    except Exception as exc:
        return {"ok": False, "error": f"Error generando PDF: {exc}"}

    return {
        "ok": True,
        "ruta": str(path),
        "tamanio_kb": round(len(data) / 1024, 1),
        "filas": len(filas),
    }


# ===========================================================================
# Entry point
# ===========================================================================
if __name__ == "__main__":
    log.info("Arrancando MCP server equivalencia-masiva-core…")
    log.info("Plugin root: %s", _PLUGIN_ROOT)
    log.info("Project root: %s", _PROJECT_ROOT)
    mcp.run()
