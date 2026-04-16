#!/usr/bin/env python
"""
CLI headless del pipeline Equivalencia Masiva — Despacho III EARM (CNSC).

Uso típico (invocado por la rutina semanal de Claude Code):

    python run_pipeline.py \\
        --input ./input/base_consolidada.xlsx \\
        --output-dir ./output \\
        --date 2026-04-16

Produce:
    ./output/resultados_2026-04-16.xlsx   (Excel consolidado con veredictos)
    ./output/reporte_2026-04-16.pdf       (PDF detallado institucional)
    ./output/resumen_2026-04-16.json      (JSON con totales — para la FASE 4 de la rutina)

Códigos de salida:
    0 — éxito total
    1 — archivo de entrada no encontrado o inválido
    2 — faltan columnas requeridas
    3 — error de dependencias (SBERT, openpyxl, etc.)
    4 — error imprevisto durante el análisis (stack trace al stderr)

Logs: todo al stderr con timestamps. El stdout está reservado para un JSON
con el resumen que la rutina parsea.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import traceback
from collections import Counter
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pandas as pd

# Logging al stderr — el stdout lo reservamos para el JSON final.
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stderr,
)
log = logging.getLogger("run_pipeline")


def _exit(code: int, message: str, extra: dict | None = None) -> None:
    """Imprime el resumen JSON en stdout y termina con el código dado."""
    payload: dict = {"ok": code == 0, "exit_code": code, "mensaje": message}
    if extra:
        payload.update(extra)
    print(json.dumps(payload, ensure_ascii=False, default=str))
    sys.exit(code)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CLI headless del pipeline Equivalencia Masiva (Despacho EARM)."
    )
    parser.add_argument("--input", required=True, help="Ruta al Excel consolidado de entrada.")
    parser.add_argument("--output-dir", required=True, help="Directorio de salida para Excel + PDF + JSON.")
    parser.add_argument(
        "--date",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Fecha ISO (AAAA-MM-DD) usada en los nombres de archivo. Default: hoy.",
    )
    parser.add_argument(
        "--limite", type=int, default=None,
        help="Si se especifica, sólo procesa los primeros N pares (smoke test rápido).",
    )
    parser.add_argument(
        "--umbral-funciones", type=float, default=0.60,
        help="Umbral de cobertura para Funciones. Default: 0.60 (notebook).",
    )
    parser.add_argument(
        "--umbral-estudio", type=float, default=0.70,
        help="Umbral de cobertura para Requisitos Estudio. Default: 0.70.",
    )
    parser.add_argument(
        "--umbral-comp", type=float, default=0.65,
        help="Umbral de cobertura para Competencias. Default: 0.65.",
    )
    parser.add_argument(
        "--sin-requisitos", action="store_true",
        help="Si se activa, NO exige estudio+competencias en la decisión (sólo funciones+gating).",
    )
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Rutas de salida con fecha ISO
    path_xlsx = output_dir / f"resultados_{args.date}.xlsx"
    path_pdf = output_dir / f"reporte_{args.date}.pdf"
    path_json = output_dir / f"resumen_{args.date}.json"

    log.info("Input:     %s", input_path)
    log.info("Output:    %s", output_dir)
    log.info("Excel:     %s", path_xlsx.name)
    log.info("PDF:       %s", path_pdf.name)

    # --- 1. Validar entrada ---
    if not input_path.exists():
        _exit(1, f"Archivo de entrada no encontrado: {input_path}")

    try:
        df = pd.read_excel(input_path)
    except Exception as exc:
        _exit(1, f"No se pudo leer el Excel: {exc}")

    # --- 2. Importar módulos del proyecto (después de validar la entrada) ---
    try:
        from core.grouping import agrupar_dataframe, validar_columnas
        from core.semantic import analizar_par, cargar_modelo, pre_cachear_embeddings
        from core.decision import decidir
        from core.report import construir_fila, exportar_excel
        from core.pdf_report import generar_pdf
    except ImportError as exc:
        _exit(3, f"Error importando módulos del proyecto: {exc}. ¿Corriste desde la raíz del proyecto?")

    # --- 3. Validar columnas ---
    faltantes = validar_columnas(df)
    if faltantes:
        _exit(
            2,
            f"Faltan {len(faltantes)} columnas requeridas: {', '.join(faltantes)}",
            {"columnas_faltantes": faltantes},
        )

    log.info("Excel válido: %d filas, %d columnas.", len(df), len(df.columns))

    # --- 4. Agrupar ---
    grupos = agrupar_dataframe(df)
    if not grupos:
        _exit(1, "No se generaron grupos. ¿El Excel tiene filas con modalidad '4.0'?")

    total_pares = sum(len(g.listas) for g in grupos)
    huerfanos = sum(1 for g in grupos if g.is_lonely)
    log.info(
        "Agrupamiento: %d grupos, %d pares a analizar, %d bases huérfanas.",
        len(grupos), total_pares, huerfanos,
    )

    if total_pares == 0:
        _exit(
            1,
            "No hay pares (base, lista) para analizar. Todas las bases 4.0 son huérfanas.",
            {"grupos": len(grupos), "huerfanos": huerfanos},
        )

    # --- 5. Cargar modelo SBERT (primera vez tarda 1-2 min) ---
    try:
        log.info("Cargando modelo SBERT (primera vez descarga ~450 MB)…")
        t0 = time.perf_counter()
        model = cargar_modelo()
        log.info("Modelo cargado en %.1fs.", time.perf_counter() - t0)
    except Exception as exc:
        _exit(3, f"Error cargando SBERT: {exc}")

    # --- 6. Pre-cachear embeddings (optimización 10x) ---
    log.info("Pre-computando embeddings de todos los textos únicos…")
    t0 = time.perf_counter()
    try:
        emb_cache = pre_cachear_embeddings(grupos, model)
    except Exception as exc:
        log.warning("Fallo pre-cache (no crítico): %s", exc)
        emb_cache = {}
    log.info("Pre-cache listo en %.1fs (%d textos únicos).", time.perf_counter() - t0, len(emb_cache))

    # --- 7. Loop de análisis ---
    filas = []
    errores_pares = []
    t0 = time.perf_counter()
    pares_procesados = 0

    for i, grupo in enumerate(grupos):
        if grupo.listas.empty:
            continue
        for _, lista_row in grupo.listas.iterrows():
            if args.limite is not None and pares_procesados >= args.limite:
                break
            try:
                aspectos = analizar_par(grupo.base, lista_row, model, emb_cache)
                decision = decidir(
                    aspectos,
                    umbral_funciones=args.umbral_funciones,
                    umbral_estudio=args.umbral_estudio,
                    umbral_comp=args.umbral_comp,
                    incluir_requisitos=not args.sin_requisitos,
                )
                filas.append(construir_fila(
                    grupo_nombre=grupo.nombre,
                    entidad=grupo.entidad,
                    base=grupo.base,
                    lista=lista_row,
                    aspectos=aspectos,
                    decision=decision,
                ))
                pares_procesados += 1
            except Exception as exc:
                errores_pares.append({
                    "grupo": grupo.nombre,
                    "opec_base": str(grupo.base.get("No. OPEC", "")),
                    "opec_lista": str(lista_row.get("No. OPEC", "")),
                    "error": str(exc),
                })
                log.warning("Error en par %s/%s: %s", grupo.base.get("No. OPEC"), lista_row.get("No. OPEC"), exc)

        if args.limite is not None and pares_procesados >= args.limite:
            break

        # Progreso cada 10 grupos
        if (i + 1) % 10 == 0:
            elapsed = time.perf_counter() - t0
            log.info("Progreso: grupo %d/%d · %d pares · %.1fs", i + 1, len(grupos), pares_procesados, elapsed)

    tiempo_analisis = time.perf_counter() - t0
    log.info("Análisis completo en %.1fs · %d pares procesados · %d errores.",
             tiempo_analisis, pares_procesados, len(errores_pares))

    if not filas:
        _exit(4, "No se procesó ningún par exitosamente.", {"errores": errores_pares})

    # --- 8. Exportar Excel consolidado ---
    try:
        xlsx_bytes = exportar_excel(filas, f"resultados_{args.date}")
        path_xlsx.write_bytes(xlsx_bytes)
        log.info("Excel escrito: %s (%d KB)", path_xlsx, len(xlsx_bytes) // 1024)
    except Exception as exc:
        log.error("Error generando Excel: %s\n%s", exc, traceback.format_exc())
        _exit(4, f"Error generando Excel: {exc}")

    # --- 9. Exportar PDF detallado ---
    try:
        pdf_bytes = generar_pdf(filas, f"resultados_{args.date}")
        path_pdf.write_bytes(pdf_bytes)
        log.info("PDF escrito:   %s (%d KB)", path_pdf, len(pdf_bytes) // 1024)
    except Exception as exc:
        log.error("Error generando PDF: %s\n%s", exc, traceback.format_exc())
        # No es crítico — seguimos con el resumen JSON
        path_pdf = None

    # --- 10. Armar resumen JSON para la rutina ---
    counter = Counter(f.decision_final for f in filas)
    total_equiv = counter.get("EQUIVALENTE", 0)
    total_no_equiv = counter.get("NO_EQUIVALENTE", 0)

    # Top 10 entidades con más pares
    entidades = Counter(f.entidad for f in filas)
    top_entidades = [
        {"entidad": ent, "pares": n, "equivalentes": sum(
            1 for f in filas if f.entidad == ent and f.es_equivalente
        )}
        for ent, n in entidades.most_common(10)
    ]

    # Distribución por Nivel Jerárquico
    niveles = Counter(f.nivel_base for f in filas)
    distribucion_nivel = [{"nivel": k, "pares": v} for k, v in niveles.most_common()]

    # Top 10 Denominaciones más frecuentes
    denoms = Counter(f.denom_lista for f in filas)
    top_denominaciones = [{"denominacion": d[:60], "apariciones": n} for d, n in denoms.most_common(10)]

    # Alertas: filas con campos críticos vacíos
    alertas = {
        "funciones_vacias": sum(1 for f in filas if not f.funciones_lista.strip()),
        "estudio_vacio": sum(1 for f in filas if not f.estudio_lista.strip()),
        "experiencia_vacia": sum(1 for f in filas if not f.experiencia_lista.strip()),
    }

    resumen = {
        "ok": True,
        "exit_code": 0,
        "mensaje": "Pipeline ejecutado exitosamente.",
        "fecha": args.date,
        "archivo_entrada": str(input_path),
        "tiempo_segundos": round(tiempo_analisis, 1),
        "total_pares_analizados": len(filas),
        "total_grupos": len(grupos),
        "bases_huerfanas": huerfanos,
        "errores_durante_analisis": len(errores_pares),
        "totales": {
            "EQUIVALENTE": total_equiv,
            "NO_EQUIVALENTE": total_no_equiv,
            "pct_equivalentes": round(total_equiv / len(filas) * 100, 1),
            "pct_no_equivalentes": round(total_no_equiv / len(filas) * 100, 1),
        },
        "top_entidades": top_entidades,
        "distribucion_nivel": distribucion_nivel,
        "top_denominaciones": top_denominaciones,
        "alertas": alertas,
        "archivos_salida": {
            "xlsx": str(path_xlsx),
            "pdf": str(path_pdf) if path_pdf else None,
            "json": str(path_json),
        },
        "errores_detalle": errores_pares[:20],  # primeros 20 para no inundar
    }

    # --- 11. Guardar JSON a disco (para que la rutina lo pueda leer aparte) ---
    try:
        path_json.write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("JSON escrito:  %s", path_json)
    except Exception as exc:
        log.warning("No pude guardar JSON: %s", exc)

    # --- 12. Emitir resumen al stdout para la rutina ---
    print(json.dumps(resumen, ensure_ascii=False, default=str))
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover
        log.error("Error fatal: %s\n%s", exc, traceback.format_exc())
        _exit(4, f"Error fatal: {exc}")
