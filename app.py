"""
Equivalencia Masiva — Despacho III EARM (CNSC).

App Streamlit que replica el análisis del notebook mismo_grado_.ipynb
sobre TODOS los empleos base 4.0 de un Excel en una sola corrida.

Arquitectura:
  1) core/grouping.py     → agrupa (entidad, nivel, grado) → grupo base 4.0 + listas
  2) core/semantic.py     → port fiel del notebook (SBERT + 5 aspectos)
  3) core/decision.py     → compuerta AND del notebook
  4) core/report.py       → Excel consolidado
  5) core/pdf_report.py   → Informe PDF detallado
  6) core/template.py     → Plantilla Excel descargable
"""

from __future__ import annotations

import time
from collections import Counter
from datetime import datetime

import pandas as pd
import streamlit as st

from config import (
    INCLUIR_REQUISITOS_EN_DECISION,
    SBERT_MODEL_FALLBACK,
    SBERT_MODEL_FAST,
    SBERT_MODEL_PRIMARY,
    UMBRAL_DECISION_COMP,
    UMBRAL_DECISION_ESTUDIO,
    UMBRAL_DECISION_FUNCIONES,
    WEIGHT_COMP_COMP,
    WEIGHT_COMP_LAB,
    WEIGHT_ESTUDIO,
    WEIGHT_FUNCIONES,
)
from core.decision import decidir
from core.grouping import agrupar_dataframe, validar_columnas
from core.pdf_report import generar_pdf
from core.report import FilaReporte, construir_fila, exportar_excel
from core.semantic import analizar_par, pre_cachear_embeddings
from core.template import generar_plantilla_excel


# =========================================================================
# Configuración de la página
# =========================================================================

st.set_page_config(
    page_title="EQUIVALENCIA MASIVA — Despacho EARM",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# -------------------------------------------------------------------------
# Sistema de diseño corporativo Despacho EARM — CNSC 2026
# Paleta:
#   #FFEE58 corp-accent  · #FDD835 hover · #F0F0F0 light
#   #424242 text         · #2C2C2C dark  · #FAFAFA body bg
# Fuentes: Plus Jakarta Sans (body) + JetBrains Mono (mono)
# -------------------------------------------------------------------------

st.markdown(
    """
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">

    <style>
      /* =====================================================================
         Base — tipografía corporativa y fondo
         ===================================================================== */
      html, body, [data-testid="stAppViewContainer"], .stApp,
      .stMarkdown, .stButton, .stDownloadButton, [data-testid="stMetric"],
      [data-testid="stExpander"], .stDataFrame {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
        -webkit-font-smoothing: antialiased;
        text-rendering: optimizeLegibility;
      }

      .stApp {
        background-color: #FAFAFA !important;
        color: #424242;
      }

      /* Orbes ambientales (yellow + emerald) — obligatorios del diseño EARM */
      .stApp::before {
        content: '';
        position: fixed;
        top: -18%; left: -8%;
        width: 384px; height: 384px;
        background: rgba(255, 238, 88, 0.22);
        border-radius: 50%;
        filter: blur(120px);
        pointer-events: none;
        z-index: 0;
      }
      .stApp::after {
        content: '';
        position: fixed;
        bottom: -18%; right: -8%;
        width: 384px; height: 384px;
        background: rgba(16, 185, 129, 0.15);
        border-radius: 50%;
        filter: blur(120px);
        pointer-events: none;
        z-index: 0;
      }

      /* Contenido principal por encima de los orbes */
      .main .block-container,
      section.main > div.block-container {
        position: relative;
        z-index: 1;
        padding-top: 1.5rem;
        max-width: 1200px;
      }

      /* Header nativo de Streamlit — transparente */
      [data-testid="stHeader"] {
        background: transparent !important;
      }

      /* =====================================================================
         Tipografía — sentence case, tildes obligatorios, sin Title Case
         ===================================================================== */
      h1, h2, h3, h4, h5, h6 {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        color: #2C2C2C !important;
        letter-spacing: -0.015em !important;
      }
      h2 { font-weight: 700 !important; font-size: 1.4rem !important; }
      h3 { font-weight: 700 !important; font-size: 1.1rem !important; }
      h4 { font-weight: 700 !important; font-size: 0.9rem !important; color: rgba(66,66,66,0.75) !important; }

      code {
        font-family: 'JetBrains Mono', monospace !important;
        background: #F0F0F0;
        color: #424242;
        padding: 2px 6px;
        border-radius: 6px;
        font-size: 0.85em;
      }

      /* =====================================================================
         Header EARM — glass morphism con logo amarillo + estado
         ===================================================================== */
      .earm-header {
        background: rgba(255, 255, 255, 0.82);
        backdrop-filter: blur(24px);
        -webkit-backdrop-filter: blur(24px);
        border: 1px solid #F0F0F0;
        border-radius: 16px;
        padding: 20px 26px;
        margin-bottom: 26px;
        box-shadow: 0 2px 8px -2px rgba(0, 0, 0, 0.04);
        display: flex;
        align-items: center;
        gap: 18px;
      }
      .earm-logo {
        width: 56px;
        height: 56px;
        background: #FFEE58;
        border-radius: 16px;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 12px 24px -10px rgba(255, 238, 88, 0.7);
        flex-shrink: 0;
        font-size: 1.9rem;
      }
      .earm-header-text {
        flex: 1;
        min-width: 0;
      }
      .earm-header-text h1 {
        font-size: 1.4rem !important;
        font-weight: 800 !important;
        color: #2C2C2C !important;
        margin: 0 !important;
        letter-spacing: -0.025em !important;
        display: flex;
        align-items: center;
        gap: 12px;
        line-height: 1.2;
      }
      .earm-version {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.58rem;
        font-weight: 700;
        background: #F0F0F0;
        color: rgba(66, 66, 66, 0.55);
        padding: 3px 7px;
        border-radius: 5px;
        letter-spacing: 0.08em;
      }
      .earm-header-text .earm-subtitle {
        margin: 4px 0 0 0;
        color: rgba(66, 66, 66, 0.72);
        font-size: 0.78rem;
        font-weight: 500;
      }
      .earm-header-text .earm-subtitle code {
        background: rgba(255, 238, 88, 0.25);
        color: #2C2C2C;
      }
      .earm-status {
        margin-left: auto;
        display: flex;
        align-items: center;
        gap: 7px;
        padding: 6px 12px;
        background: rgba(16, 185, 129, 0.08);
        border: 1px solid rgba(16, 185, 129, 0.2);
        border-radius: 999px;
        flex-shrink: 0;
      }
      .earm-status-dot {
        width: 8px;
        height: 8px;
        background: #10b981;
        border-radius: 50%;
        animation: earm-pulse 2s ease-in-out infinite;
      }
      @keyframes earm-pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50%      { opacity: 0.55; transform: scale(0.9); }
      }
      .earm-status-label {
        font-size: 0.6rem;
        font-weight: 700;
        color: #047857;
        text-transform: uppercase;
        letter-spacing: 0.12em;
      }

      /* =====================================================================
         Botones — primario amarillo, secundario borde, siempre uppercase
         ===================================================================== */
      .stButton > button,
      .stDownloadButton > button {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.025em !important;
        border-radius: 12px !important;
        padding: 10px 20px !important;
        font-size: 0.78rem !important;
        transition: all 0.2s !important;
        border: 1px solid #F0F0F0 !important;
        background: white !important;
        color: #424242 !important;
      }
      .stButton > button:hover,
      .stDownloadButton > button:hover {
        border-color: #FFEE58 !important;
        background: #FFFBE6 !important;
        color: #2C2C2C !important;
      }

      /* Primary variant — amarillo accent */
      .stButton > button[kind="primary"],
      .stDownloadButton > button[kind="primary"] {
        background: #FFEE58 !important;
        color: #2C2C2C !important;
        border: none !important;
        box-shadow: 0 4px 10px -3px rgba(255, 238, 88, 0.55) !important;
      }
      .stButton > button[kind="primary"]:hover,
      .stDownloadButton > button[kind="primary"]:hover {
        background: #FDD835 !important;
        box-shadow: 0 6px 14px -3px rgba(253, 216, 53, 0.7) !important;
        transform: translateY(-1px);
      }
      .stDownloadButton > button { width: 100% !important; }

      /* =====================================================================
         File uploader — glass + accent en hover
         ===================================================================== */
      [data-testid="stFileUploader"] section,
      [data-testid="stFileUploaderDropzone"] {
        background: rgba(255, 255, 255, 0.8) !important;
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 2px dashed #F0F0F0 !important;
        border-radius: 16px !important;
        padding: 22px !important;
        transition: all 0.2s !important;
      }
      [data-testid="stFileUploader"] section:hover,
      [data-testid="stFileUploaderDropzone"]:hover {
        border-color: #FFEE58 !important;
        background: rgba(255, 251, 230, 0.8) !important;
      }
      [data-testid="stFileUploader"] small {
        color: rgba(66,66,66,0.55) !important;
        font-weight: 600;
      }

      /* =====================================================================
         Metric cards — glass morphism
         ===================================================================== */
      [data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.82) !important;
        backdrop-filter: blur(24px);
        -webkit-backdrop-filter: blur(24px);
        border: 1px solid #F0F0F0;
        border-radius: 16px;
        padding: 16px 18px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
        transition: box-shadow 0.2s;
      }
      [data-testid="stMetric"]:hover {
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
      }
      [data-testid="stMetricLabel"] p,
      [data-testid="stMetricLabel"] {
        font-size: 0.68rem !important;
        font-weight: 700 !important;
        color: rgba(66, 66, 66, 0.55) !important;
        text-transform: uppercase !important;
        letter-spacing: 0.1em !important;
      }
      [data-testid="stMetricValue"] {
        font-size: 1.85em !important;
        color: #2C2C2C !important;
        font-weight: 800 !important;
        letter-spacing: -0.02em;
      }

      /* =====================================================================
         Expanders — glass + accent
         ===================================================================== */
      [data-testid="stExpander"] {
        background: rgba(255, 255, 255, 0.82) !important;
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid #F0F0F0 !important;
        border-radius: 16px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.03);
      }
      [data-testid="stExpander"] details summary {
        font-weight: 700 !important;
        color: #2C2C2C !important;
        padding: 14px 18px !important;
        font-size: 0.88rem;
      }
      [data-testid="stExpander"] details summary:hover {
        background: rgba(255, 238, 88, 0.08);
        border-radius: 16px;
      }

      /* =====================================================================
         Alerts (info/success/warning/error) con colores semánticos Tailwind
         ===================================================================== */
      [data-testid="stAlert"] {
        border-radius: 12px !important;
        border-left-width: 4px !important;
        backdrop-filter: blur(12px);
      }

      /* =====================================================================
         Sliders — handle amarillo
         ===================================================================== */
      [data-testid="stSlider"] [role="slider"] {
        background: #FFEE58 !important;
        border: 2px solid #FDD835 !important;
        box-shadow: 0 2px 6px rgba(255, 238, 88, 0.6) !important;
      }
      [data-testid="stSlider"] [data-baseweb="slider"] div[role="progressbar"] {
        background: linear-gradient(90deg, #FDD835, #FFEE58) !important;
      }

      /* =====================================================================
         Progress bar
         ===================================================================== */
      [data-testid="stProgress"] > div > div > div > div {
        background: linear-gradient(90deg, #FFEE58, #FDD835) !important;
      }

      /* =====================================================================
         DataFrames — bordes redondeados
         ===================================================================== */
      [data-testid="stDataFrame"],
      [data-testid="stTable"] {
        border-radius: 16px !important;
        overflow: hidden !important;
        border: 1px solid #F0F0F0 !important;
        background: rgba(255,255,255,0.82) !important;
        backdrop-filter: blur(16px);
      }
      [data-testid="stDataFrame"] thead th {
        background: #F0F0F0 !important;
        color: rgba(66,66,66,0.6) !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.08em !important;
        font-size: 0.65rem !important;
      }

      /* =====================================================================
         Checkbox — accent
         ===================================================================== */
      [data-testid="stCheckbox"] label span[role="checkbox"][aria-checked="true"] {
        background: #FFEE58 !important;
        border-color: #FDD835 !important;
      }

      /* =====================================================================
         Selectbox — border radius consistente
         ===================================================================== */
      [data-baseweb="select"] > div {
        border-radius: 12px !important;
        border-color: #F0F0F0 !important;
      }
      [data-baseweb="select"] > div:hover {
        border-color: #FFEE58 !important;
      }

      /* =====================================================================
         Footer EARM
         ===================================================================== */
      .earm-footer {
        margin-top: 48px;
        padding: 18px 24px;
        border: 1px solid #F0F0F0;
        background: rgba(255, 255, 255, 0.82);
        backdrop-filter: blur(24px);
        -webkit-backdrop-filter: blur(24px);
        text-align: center;
        font-size: 0.62rem;
        font-weight: 700;
        color: rgba(66, 66, 66, 0.72);
        text-transform: uppercase;
        letter-spacing: 0.16em;
        border-radius: 12px;
        position: relative;
        z-index: 1;
      }
      .earm-footer .accent {
        color: #2C2C2C;
      }

      /* =====================================================================
         Scrollbar corporativa
         ===================================================================== */
      ::-webkit-scrollbar { width: 10px; height: 10px; }
      ::-webkit-scrollbar-track { background: #F0F0F0; }
      ::-webkit-scrollbar-thumb {
        background: #ccc;
        border-radius: 5px;
        border: 2px solid #F0F0F0;
      }
      ::-webkit-scrollbar-thumb:hover { background: #aaa; }
    </style>

    <div class="earm-header">
      <div class="earm-logo">⚖️</div>
      <div class="earm-header-text">
        <h1>
          EQUIVALENCIA MASIVA
          <span class="earm-version">v1.0</span>
        </h1>
        <p class="earm-subtitle">
          Análisis masivo de listas de elegibles — Despacho III — Comisionado Edwin Arturo Ruiz Moreno · CNSC
        </p>
      </div>
      <div class="earm-status">
        <div class="earm-status-dot"></div>
        <span class="earm-status-label">En línea</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================================
# Carga del modelo SBERT (cacheada)
# =========================================================================

@st.cache_resource(show_spinner=False)
def _load_sbert(nombre_modelo: str):
    from core.semantic import cargar_modelo
    return cargar_modelo(nombre_modelo)


# =========================================================================
# Estado de sesión
# =========================================================================

for key, default in [
    ("df_empleos", None),
    ("grupos", []),
    ("filas_reporte", []),
    ("excel_bytes", None),
    ("pdf_bytes", None),
    ("nombre_archivo", ""),
    ("tiempo_ultimo", 0.0),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# =========================================================================
# Sección: Instructivo (expander colapsable)
# =========================================================================

with st.expander("📘 Instructivo de uso (click para expandir)", expanded=False):
    st.markdown(
        """
        ### Cómo usar esta aplicación

        **Paso 1 — Descargar plantilla (opcional).**
        Si no tienes un Excel previo en el formato correcto, baja la plantilla
        desde el botón más abajo. Viene con 3 filas de ejemplo y los encabezados
        con tooltips que explican cada columna.

        **Paso 2 — Cargar el Excel.**
        Arrastra o selecciona el archivo `.xlsx`. La app valida las 15 columnas
        requeridas (las mismas que el notebook `mismo_grado_.ipynb` del Despacho).

        **Paso 3 — Configurar (opcional).**
        Los umbrales y pesos vienen con los mismos valores default del notebook:
        - Funciones ≥ 60%  · Estudio ≥ 70%  · Competencias ≥ 65%
        - Pesos ponderado final: Funciones 0.80 · Estudio 0.20 · Competencias 0.00

        **Paso 4 — Ejecutar análisis.**
        Click en "Ejecutar análisis masivo". La app:
          1. Agrupa cada empleo base 4.0 con sus listas del mismo grado/nivel/entidad.
          2. Para cada par (base, lista) calcula cobertura semántica SBERT sobre los 5
             aspectos: Funciones, Estudio, Comp. Laborales, Comp. Comportamentales y
             Experiencia (con jerarquía).
          3. Aplica la compuerta AND del notebook → Decisión final.

        **Paso 5 — Descargar resultados.**
        - **Excel consolidado**: tabla pivoteable con 1 fila por par (base, lista), scores,
          razones y textos originales.
        - **PDF detallado**: informe con portada, resumen ejecutivo, desglose por grupo
          y detalle par por par con scores y razones.

        ### Lógica de equivalencia (idéntica al notebook)

        Un par `(base, lista)` es **EQUIVALENTE** si cumple TODAS estas condiciones:

        1. Mismo Nivel Jerárquico (idéntico después de normalizar).
        2. Mismo Grado y diferencia salarial ≤ 10%.
        3. Cobertura SBERT de Funciones ≥ Umbral Funciones (default 60%).
        4. Si **"Incluir Requisitos"** está activo:
           - Cobertura Requisitos Estudio ≥ Umbral Estudio (default 70%).
           - Cobertura Competencias Laborales ≥ Umbral Competencias (default 65%).
           - Cobertura Competencias Comportamentales ≥ Umbral Competencias (default 65%).

        Si falla CUALQUIERA de las condiciones anteriores → **NO EQUIVALENTE**.

        El **score ponderado final** se calcula como:

        ```
        score = (func × 0.80 + estudio × 0.20 + comp_lab × 0.00 + comp_comp × 0.00)
              / (0.80 + 0.20 + 0.00 + 0.00)
        ```
        """
    )


# =========================================================================
# Sección 0: Descargar plantilla
# =========================================================================

st.subheader("0. Descargar plantilla (opcional)")
col_t1, col_t2 = st.columns([1, 3])
with col_t1:
    st.download_button(
        "📄 Descargar plantilla .xlsx",
        data=generar_plantilla_excel(),
        file_name="plantilla_equivalencia_masiva.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        help="Baja la plantilla con encabezados, tooltips y 3 filas de ejemplo.",
    )
with col_t2:
    st.caption(
        "Incluye las 15 columnas requeridas, comentarios explicativos en cada encabezado, "
        "3 filas de ejemplo (1 empleo base 4.0 + 2 listas) y una pestaña de instrucciones."
    )


# =========================================================================
# Sección 1: Cargar Excel
# =========================================================================

st.subheader("1. Cargar Excel de OPEC")
uploaded = st.file_uploader(
    "Sube el Excel con los empleos base 4.0 y sus listas candidatas",
    type=["xlsx", "xls"],
    help="El archivo debe contener las 15 columnas de la plantilla.",
)

if uploaded is not None:
    try:
        df = pd.read_excel(uploaded)
    except Exception as exc:
        st.error(f"Error leyendo el Excel: {exc}")
        st.stop()

    faltantes = validar_columnas(df)
    if faltantes:
        st.error(
            "Faltan columnas requeridas en el Excel: "
            + ", ".join(f"`{c}`" for c in faltantes)
            + ". Descarga la plantilla para ver el formato esperado."
        )
        st.stop()

    st.session_state.df_empleos = df
    st.session_state.nombre_archivo = uploaded.name
    st.session_state.grupos = agrupar_dataframe(df)
    st.session_state.filas_reporte = []
    st.session_state.excel_bytes = None
    st.session_state.pdf_bytes = None

    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Filas leídas", len(df))
    col_b.metric("Grupos (bases 4.0)", len(st.session_state.grupos))
    total_pares = sum(len(g.listas) for g in st.session_state.grupos)
    col_c.metric("Pares (base, lista)", total_pares)
    huerfanos = sum(1 for g in st.session_state.grupos if g.is_lonely)
    col_d.metric("Bases sin listas", huerfanos, help="Bases 4.0 sin ninguna lista candidata del mismo grado.")

    with st.expander("Previsualización del Excel (primeras 20 filas)"):
        st.dataframe(df.head(20), use_container_width=True)


# =========================================================================
# Sección 2: Configuración
# =========================================================================

if st.session_state.grupos:
    st.subheader("2. Configuración del análisis")

    with st.expander("Modelo semántico, umbrales y pesos", expanded=False):
        col1, col2 = st.columns(2)

        modelo_labels = {
            SBERT_MODEL_PRIMARY: "STS Spanish (fiel al notebook, recomendado) — ~450 MB",
            SBERT_MODEL_FALLBACK: "MPNet Multilingüe (segunda opción del notebook) — ~500 MB",
            SBERT_MODEL_FAST: "MiniLM Multilingüe (rápido, resultados muy cercanos) — ~120 MB",
        }
        modelo_elegido = col1.selectbox(
            "Modelo SBERT",
            options=list(modelo_labels.keys()),
            format_func=lambda x: modelo_labels[x],
            index=0,
            help="STS Spanish es el modelo de referencia del notebook para fidelidad 1:1.",
        )

        incluir_reqs = col2.checkbox(
            "Incluir requisitos en la decisión (Estudio, Comp. Laborales, Comp. Comportamentales)",
            value=INCLUIR_REQUISITOS_EN_DECISION,
            help="Replica `chk_incluir_requisitos` del notebook — default: activo.",
        )

        st.markdown("**Umbrales de decisión** (mismos valores default del notebook)")
        col3, col4, col5 = st.columns(3)
        umbral_func = col3.slider(
            "Umbral Funciones ≥",
            min_value=0.0, max_value=1.0, value=UMBRAL_DECISION_FUNCIONES, step=0.01,
        )
        umbral_est = col4.slider(
            "Umbral Requisitos Estudio ≥",
            min_value=0.0, max_value=1.0, value=UMBRAL_DECISION_ESTUDIO, step=0.01,
        )
        umbral_comp = col5.slider(
            "Umbral Competencias (Lab./Comp.) ≥",
            min_value=0.0, max_value=1.0, value=UMBRAL_DECISION_COMP, step=0.01,
        )

        st.markdown("**Pesos para el score ponderado** (deberían sumar 1.0)")
        col6, col7, col8, col9 = st.columns(4)
        peso_f = col6.slider("Funciones", 0.0, 1.0, WEIGHT_FUNCIONES, 0.05)
        peso_e = col7.slider("Estudio", 0.0, 1.0, WEIGHT_ESTUDIO, 0.05)
        peso_l = col8.slider("Comp. Lab.", 0.0, 1.0, WEIGHT_COMP_LAB, 0.05)
        peso_c = col9.slider("Comp. Comp.", 0.0, 1.0, WEIGHT_COMP_COMP, 0.05)
    # Persistir config en session state (por si el usuario cambia y re-ejecuta)
    st.session_state.cfg = dict(
        modelo=modelo_elegido,
        incluir_reqs=incluir_reqs,
        umbral_func=umbral_func,
        umbral_est=umbral_est,
        umbral_comp=umbral_comp,
        peso_f=peso_f, peso_e=peso_e, peso_l=peso_l, peso_c=peso_c,
    )


# =========================================================================
# Sección 3: Ejecutar análisis
# =========================================================================

if st.session_state.grupos:
    st.subheader("3. Ejecutar análisis masivo")

    total_pares = sum(len(g.listas) for g in st.session_state.grupos)
    st.info(
        f"Se analizarán **{total_pares} pares** (base 4.0 ↔ lista) en "
        f"**{len(st.session_state.grupos)} grupos**. "
        f"El modelo seleccionado se descarga automáticamente la primera vez "
        f"(~450 MB para STS Spanish, puede tardar 1-2 minutos con buena conexión)."
    )

    if st.button("▶️ Ejecutar análisis masivo", type="primary"):
        cfg = st.session_state.cfg
        filas: list[FilaReporte] = []
        start = time.perf_counter()

        with st.spinner("Cargando modelo semántico… (primera vez tarda 1-2 minutos)"):
            model = _load_sbert(cfg["modelo"])

        # Pre-cachear embeddings de todos los textos únicos
        with st.spinner("Pre-computando embeddings de textos únicos (acelera x10 el análisis masivo)…"):
            embeddings_cache = pre_cachear_embeddings(st.session_state.grupos, model)

        progress = st.progress(0.0)
        log = st.empty()

        total_evaluados = 0
        for i, grupo in enumerate(st.session_state.grupos):
            if grupo.listas.empty:
                progress.progress((i + 1) / len(st.session_state.grupos))
                continue

            for _, lista_row in grupo.listas.iterrows():
                try:
                    aspectos = analizar_par(
                        grupo.base, lista_row, model, embeddings_cache
                    )
                    decision = decidir(
                        aspectos,
                        umbral_funciones=cfg["umbral_func"],
                        umbral_estudio=cfg["umbral_est"],
                        umbral_comp=cfg["umbral_comp"],
                        incluir_requisitos=cfg["incluir_reqs"],
                        peso_funciones=cfg["peso_f"],
                        peso_estudio=cfg["peso_e"],
                        peso_comp_lab=cfg["peso_l"],
                        peso_comp_comp=cfg["peso_c"],
                    )
                    filas.append(
                        construir_fila(
                            grupo_nombre=grupo.nombre,
                            entidad=grupo.entidad,
                            base=grupo.base,
                            lista=lista_row,
                            aspectos=aspectos,
                            decision=decision,
                        )
                    )
                    total_evaluados += 1
                except Exception as exc:
                    st.warning(f"Fallo en un par de `{grupo.nombre}`: {exc}")
                    continue

            elapsed = time.perf_counter() - start
            avg = elapsed / max(total_evaluados, 1)
            remaining = (total_pares - total_evaluados) * avg
            log.text(
                f"Grupo {i + 1}/{len(st.session_state.grupos)} · "
                f"Pares analizados: {total_evaluados}/{total_pares} · "
                f"Tiempo: {elapsed:.1f}s · ETA: {remaining:.1f}s"
            )
            progress.progress((i + 1) / len(st.session_state.grupos))

        progress.progress(1.0)
        elapsed = time.perf_counter() - start
        st.session_state.filas_reporte = filas
        st.session_state.tiempo_ultimo = elapsed
        st.session_state.excel_bytes = exportar_excel(filas, st.session_state.nombre_archivo)
        st.session_state.pdf_bytes = None  # se genera bajo demanda (es pesado)
        st.success(f"✅ Análisis completado en {elapsed:.1f}s · {total_evaluados} pares evaluados.")


# =========================================================================
# Sección 4: Resultados
# =========================================================================

if st.session_state.filas_reporte:
    st.subheader("4. Resultados")
    counter = Counter(f.decision_final for f in st.session_state.filas_reporte)

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("✅ Equivalentes", counter.get("EQUIVALENTE", 0))
    col_b.metric("❌ No equivalentes", counter.get("NO_EQUIVALENTE", 0))
    col_c.metric("Total pares", len(st.session_state.filas_reporte))

    # Descargas
    st.markdown("#### Descargar reportes")
    col_d1, col_d2 = st.columns(2)
    ts = datetime.now().strftime("%Y%m%d_%H%M")

    if st.session_state.excel_bytes:
        col_d1.download_button(
            "⬇️ Descargar Excel consolidado",
            data=st.session_state.excel_bytes,
            file_name=f"Equivalencia_Masiva_{ts}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )

    # PDF bajo demanda (puede ser pesado para lotes grandes)
    if col_d2.button("🔨 Generar informe PDF detallado", help="Puede tardar 5-20 segundos según la cantidad de pares."):
        with st.spinner("Generando PDF…"):
            st.session_state.pdf_bytes = generar_pdf(
                st.session_state.filas_reporte,
                st.session_state.nombre_archivo,
            )

    if st.session_state.pdf_bytes:
        st.download_button(
            "⬇️ Descargar PDF detallado",
            data=st.session_state.pdf_bytes,
            file_name=f"Equivalencia_Masiva_{ts}.pdf",
            mime="application/pdf",
        )

    # Filtro en pantalla
    st.markdown("#### Revisión rápida en pantalla")
    solo_equivs = st.checkbox("Mostrar solo EQUIVALENTES", value=False)
    filas = st.session_state.filas_reporte
    if solo_equivs:
        filas = [f for f in filas if f.es_equivalente]

    if filas:
        df_view = pd.DataFrame([
            {
                "Entidad": f.entidad,
                "Grupo": f.grupo,
                "OPEC Base": f.opec_base,
                "OPEC Lista": f.opec_lista,
                "Denom. Lista": f.denom_lista[:40],
                "Decisión": f.decision_final,
                "Score": f"{f.score_ponderado:.1%}",
                "Func": f"{f.sbert_funciones:.1%}",
                "Est": f"{f.sbert_estudio:.1%}",
                "C.Lab": f"{f.sbert_comp_lab:.1%}",
                "C.Com": f"{f.sbert_comp_comp:.1%}",
                "Exp": f"{f.sbert_experiencia:.1%}",
                "Nivel": "✓" if f.nivel_pasa else "✗",
                "Salario": "✓" if f.salario_pasa else "✗",
            }
            for f in filas
        ])
        st.dataframe(df_view, use_container_width=True, hide_index=True)

        # Detalle con razones al hacer click
        with st.expander("Ver razones de no equivalencia detalladas"):
            for f in filas:
                if f.razones_no_eq:
                    st.markdown(
                        f"- **{f.opec_base} ↔ {f.opec_lista}** ({f.grupo}): {f.razones_no_eq}"
                    )
    else:
        st.info("No hay filas que cumplan el filtro actual.")


# =========================================================================
# Footer EARM
# =========================================================================

st.markdown(
    """
    <div class="earm-footer">
      <span class="accent">EQUIVALENCIA MASIVA v1.0</span>
      — Análisis masivo de listas de elegibles —
      Edwin Arturo Ruiz Moreno — Comisionado CNSC 2026
    </div>
    """,
    unsafe_allow_html=True,
)
