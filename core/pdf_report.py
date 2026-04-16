"""
Generador de informe PDF consolidado usando reportlab.

Estructura:
  1. Portada con título, metadatos del Despacho EARM y fecha.
  2. Resumen ejecutivo — totales por clasificación.
  3. Por cada grupo: tabla comparativa con los pares (base, lista) y su decisión.
  4. Detalle por par: scores SBERT por aspecto, razones y textos originales.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    KeepInFrame,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from core.report import FilaReporte


# =========================================================================
# Estilos
# =========================================================================

_COLOR_HEADER = colors.HexColor("#1F3864")
_COLOR_HEADER_LIGHT = colors.HexColor("#DDEBF7")
_COLOR_EQUIVALENTE = colors.HexColor("#C6EFCE")
_COLOR_NO_EQUIVALENTE = colors.HexColor("#FFC7CE")
_COLOR_NEUTRAL = colors.HexColor("#F2F2F2")


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="DespachoTitle",
        parent=styles["Title"],
        fontSize=22,
        textColor=_COLOR_HEADER,
        alignment=TA_CENTER,
        spaceAfter=12,
    ))
    styles.add(ParagraphStyle(
        name="DespachoSubtitle",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.grey,
        alignment=TA_CENTER,
        spaceAfter=20,
    ))
    styles.add(ParagraphStyle(
        name="SectionH1",
        parent=styles["Heading1"],
        fontSize=15,
        textColor=_COLOR_HEADER,
        spaceAfter=8,
        spaceBefore=14,
    ))
    styles.add(ParagraphStyle(
        name="SectionH2",
        parent=styles["Heading2"],
        fontSize=12,
        textColor=_COLOR_HEADER,
        spaceAfter=4,
        spaceBefore=10,
    ))
    styles.add(ParagraphStyle(
        name="BodyJust",
        parent=styles["Normal"],
        fontSize=9,
        alignment=TA_JUSTIFY,
        spaceAfter=4,
        leading=11,
    ))
    styles.add(ParagraphStyle(
        name="BodySmall",
        parent=styles["Normal"],
        fontSize=8,
        alignment=TA_LEFT,
        leading=10,
    ))
    styles.add(ParagraphStyle(
        name="BodyMono",
        parent=styles["Normal"],
        fontSize=8,
        fontName="Courier",
        leading=10,
    ))
    return styles


# =========================================================================
# Helpers
# =========================================================================


def _pct(v) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.1%}"
    except Exception:
        return "—"


def _si_no(v) -> str:
    if v is True:
        return "Sí"
    if v is False:
        return "No"
    return "—"


def _truncate(s: str, n: int = 400) -> str:
    s = (s or "").strip()
    if len(s) > n:
        return s[: n - 1] + "…"
    return s


def _agrupar_por_grupo(filas: Iterable[FilaReporte]) -> dict[str, list[FilaReporte]]:
    out: dict[str, list[FilaReporte]] = {}
    for f in filas:
        out.setdefault(f.grupo, []).append(f)
    return out


# =========================================================================
# Secciones
# =========================================================================


def _portada(styles, nombre_archivo: str) -> list:
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    return [
        Spacer(1, 3 * cm),
        Paragraph("⚖ EQUIVALENCIA MASIVA DE EMPLEOS", styles["DespachoTitle"]),
        Paragraph(
            "Informe automatizado de análisis de listas de elegibles",
            styles["DespachoSubtitle"],
        ),
        Spacer(1, 2 * cm),
        Paragraph(
            "Despacho III — Comisionado Edwin Arturo Ruiz Moreno",
            styles["Heading3"],
        ),
        Paragraph("Comisión Nacional del Servicio Civil (CNSC)", styles["Heading3"]),
        Spacer(1, 1.5 * cm),
        Paragraph(f"<b>Archivo analizado:</b> {nombre_archivo}", styles["BodyJust"]),
        Paragraph(f"<b>Fecha del análisis:</b> {fecha}", styles["BodyJust"]),
        Paragraph(
            "<b>Motor semántico:</b> SBERT (faithful port de mismo_grado_.ipynb)",
            styles["BodyJust"],
        ),
        PageBreak(),
    ]


def _resumen_ejecutivo(styles, filas: list[FilaReporte]) -> list:
    total = len(filas)
    equiv = sum(1 for f in filas if f.decision_final == "EQUIVALENTE")
    no_equiv = total - equiv
    pct_equiv = (equiv / total * 100) if total else 0

    bloques = [
        Paragraph("1. Resumen Ejecutivo", styles["SectionH1"]),
        Spacer(1, 0.2 * cm),
        Paragraph(
            f"Se analizaron <b>{total} pares</b> (empleo base vigente 4.0 ↔ lista de "
            f"elegibles) provenientes de <b>{len(_agrupar_por_grupo(filas))} grupos</b> "
            f"distintos. Del total, <b>{equiv} pares ({pct_equiv:.1f}%)</b> fueron "
            f"clasificados como EQUIVALENTE según los umbrales del notebook "
            f"mismo_grado_.ipynb, mientras que <b>{no_equiv}</b> resultaron NO EQUIVALENTE.",
            styles["BodyJust"],
        ),
        Spacer(1, 0.3 * cm),
    ]

    # Tabla resumen
    data = [
        ["Clasificación", "Pares", "Porcentaje"],
        ["EQUIVALENTE", str(equiv), f"{pct_equiv:.1f}%"],
        ["NO EQUIVALENTE", str(no_equiv), f"{100 - pct_equiv:.1f}%"],
        ["TOTAL", str(total), "100.0%"],
    ]
    tabla = Table(data, colWidths=[6 * cm, 3 * cm, 3 * cm])
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _COLOR_HEADER),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("BACKGROUND", (0, 1), (-1, 1), _COLOR_EQUIVALENTE),
        ("BACKGROUND", (0, 2), (-1, 2), _COLOR_NO_EQUIVALENTE),
        ("BACKGROUND", (0, 3), (-1, 3), _COLOR_HEADER_LIGHT),
        ("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    bloques.append(tabla)
    bloques.append(Spacer(1, 0.5 * cm))

    # Desglose por entidad (top 10)
    from collections import Counter

    entidades = Counter(f.entidad for f in filas)
    if entidades:
        bloques.append(Paragraph("Desglose por entidad", styles["SectionH2"]))
        data_ent = [["Entidad", "Pares analizados"]]
        for ent, n in entidades.most_common(10):
            data_ent.append([_truncate(ent, 60), str(n)])
        tabla_ent = Table(data_ent, colWidths=[13 * cm, 3 * cm])
        tabla_ent.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _COLOR_HEADER),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _COLOR_NEUTRAL]),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        bloques.append(tabla_ent)

    bloques.append(PageBreak())
    return bloques


def _detalle_par(styles, fila: FilaReporte) -> list:
    """Genera el detalle de un par (base, lista) con scores y textos."""
    color_deco = _COLOR_EQUIVALENTE if fila.es_equivalente else _COLOR_NO_EQUIVALENTE

    bloques = [
        Paragraph(
            f"<b>OPEC Lista {fila.opec_lista}</b> — {_truncate(fila.denom_lista, 70)}",
            styles["SectionH2"],
        ),
    ]

    # Tabla de identificación
    id_data = [
        ["", "Base (4.0)", "Lista candidata"],
        ["OPEC", str(fila.opec_base), str(fila.opec_lista)],
        ["Código", str(fila.codigo_base), str(fila.codigo_lista)],
        ["Denominación", _truncate(fila.denom_base, 30), _truncate(fila.denom_lista, 30)],
        ["Grado", str(fila.grado_base), str(fila.grado_lista)],
        ["Nivel", fila.nivel_base, fila.nivel_lista],
        ["Salario", f"{fila.salario_base:,.0f}", f"{fila.salario_lista:,.0f}"],
    ]
    tabla_id = Table(id_data, colWidths=[3 * cm, 6.5 * cm, 6.5 * cm])
    tabla_id.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _COLOR_HEADER),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    bloques.append(tabla_id)
    bloques.append(Spacer(1, 0.2 * cm))

    # Tabla de scores SBERT
    scores_data = [
        ["Aspecto", "Cobertura SBERT", "Umbral", "Pasa"],
        ["Funciones", _pct(fila.sbert_funciones), "60%", _si_no(fila.pasa_funciones)],
        ["Requisitos Estudio", _pct(fila.sbert_estudio), "70%", _si_no(fila.pasa_estudio)],
        ["Comp. Laborales", _pct(fila.sbert_comp_lab), "65%", _si_no(fila.pasa_comp_lab)],
        ["Comp. Comportamentales", _pct(fila.sbert_comp_comp), "65%", _si_no(fila.pasa_comp_comp)],
        ["Experiencia (informativo)", _pct(fila.sbert_experiencia), "—", "—"],
        ["Nivel Jerárquico", "—", "=", _si_no(fila.nivel_pasa)],
        ["Salario / Grado", "—", "=", _si_no(fila.salario_pasa)],
    ]
    tabla_sc = Table(scores_data, colWidths=[6 * cm, 3.5 * cm, 2 * cm, 2 * cm])
    style_scores = [
        ("BACKGROUND", (0, 0), (-1, 0), _COLOR_HEADER),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
    ]
    # Colorear filas por pasa/no pasa
    for row_idx, pasa in enumerate(
        [fila.pasa_funciones, fila.pasa_estudio, fila.pasa_comp_lab, fila.pasa_comp_comp, None,
         fila.nivel_pasa, fila.salario_pasa],
        start=1,
    ):
        if pasa is True:
            style_scores.append(("BACKGROUND", (0, row_idx), (-1, row_idx), _COLOR_EQUIVALENTE))
        elif pasa is False:
            style_scores.append(("BACKGROUND", (0, row_idx), (-1, row_idx), _COLOR_NO_EQUIVALENTE))
    tabla_sc.setStyle(TableStyle(style_scores))
    bloques.append(tabla_sc)
    bloques.append(Spacer(1, 0.15 * cm))

    # Decisión final
    decision_texto = (
        f"<b>Decisión final:</b> <font color='#006100'>{fila.decision_final}</font>"
        if fila.es_equivalente
        else f"<b>Decisión final:</b> <font color='#9C0006'>{fila.decision_final}</font>"
    )
    decision_texto += f" &nbsp;&nbsp;&nbsp;<b>Score ponderado:</b> {_pct(fila.score_ponderado)}"
    bloques.append(Paragraph(decision_texto, styles["BodyJust"]))

    if fila.razones_no_eq:
        bloques.append(
            Paragraph(f"<b>Razones de no equivalencia:</b> {fila.razones_no_eq}", styles["BodySmall"])
        )
    if fila.exp_jerarquia_msg:
        bloques.append(
            Paragraph(f"<b>Jerarquía experiencia:</b> {fila.exp_jerarquia_msg}", styles["BodySmall"])
        )

    bloques.append(Spacer(1, 0.3 * cm))
    return bloques


def _seccion_grupo(styles, nombre_grupo: str, filas_grupo: list[FilaReporte]) -> list:
    """Sección por grupo: encabezado + cada par (base, lista)."""
    bloques = [
        Paragraph(f"Grupo: {nombre_grupo}", styles["SectionH1"]),
        Paragraph(
            f"<b>Entidad:</b> {filas_grupo[0].entidad} · "
            f"<b>Nivel:</b> {filas_grupo[0].nivel_base} · "
            f"<b>Grado:</b> {filas_grupo[0].grado_base} · "
            f"<b>OPEC Base 4.0:</b> {filas_grupo[0].opec_base} "
            f"({_truncate(filas_grupo[0].denom_base, 60)})",
            styles["BodySmall"],
        ),
        Spacer(1, 0.2 * cm),
    ]

    # Tabla-resumen del grupo
    data = [["OPEC Lista", "Denominación", "Decisión", "Score", "Func", "Est", "C.Lab", "C.Com"]]
    for f in filas_grupo:
        data.append([
            str(f.opec_lista),
            _truncate(f.denom_lista, 28),
            f.decision_final,
            _pct(f.score_ponderado),
            _pct(f.sbert_funciones),
            _pct(f.sbert_estudio),
            _pct(f.sbert_comp_lab),
            _pct(f.sbert_comp_comp),
        ])
    tabla = Table(data, colWidths=[1.8 * cm, 5 * cm, 2.6 * cm, 1.6 * cm, 1.4 * cm, 1.4 * cm, 1.4 * cm, 1.4 * cm])
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), _COLOR_HEADER),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]
    # Colorear columna Decisión por clasificación
    for r, f in enumerate(filas_grupo, start=1):
        color = _COLOR_EQUIVALENTE if f.es_equivalente else _COLOR_NO_EQUIVALENTE
        style.append(("BACKGROUND", (2, r), (2, r), color))
    tabla.setStyle(TableStyle(style))
    bloques.append(tabla)
    bloques.append(Spacer(1, 0.3 * cm))

    # Detalles por cada par
    for f in filas_grupo:
        bloques.extend(_detalle_par(styles, f))

    bloques.append(PageBreak())
    return bloques


# =========================================================================
# Entry point
# =========================================================================


def generar_pdf(filas: list[FilaReporte], nombre_archivo: str = "reporte") -> bytes:
    """
    Genera un PDF completo con el análisis masivo y devuelve los bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=f"Equivalencia Masiva — {nombre_archivo}",
        author="Despacho III CNSC - Comisionado Edwin Arturo Ruiz Moreno",
    )

    styles = _styles()
    story: list = []

    story.extend(_portada(styles, nombre_archivo))
    story.extend(_resumen_ejecutivo(styles, filas))

    # Detalle por grupo
    story.append(Paragraph("2. Detalle por Grupo", styles["SectionH1"]))
    grupos = _agrupar_por_grupo(filas)
    for grupo_nombre in sorted(grupos.keys()):
        story.extend(_seccion_grupo(styles, grupo_nombre, grupos[grupo_nombre]))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
