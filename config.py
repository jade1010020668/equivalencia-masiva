"""
Configuración central — valores tomados del notebook mismo_grado_.ipynb
para que los resultados de la app masiva sean idénticos a los del notebook.

Regla de oro: si el notebook produce X, la app DEBE producir X. Cualquier
divergencia es un bug.
"""

# --- Modelo SBERT ---
# Default del notebook (DEFAULT_MODEL_ORDER[0]): STS RoBERTa-BNE Español.
# Es el modelo que el notebook usa como "referencia" cuando hay varios.
SBERT_MODEL_PRIMARY = "hiiamsid/sentence_similarity_spanish_es"

# Segundo modelo del notebook (DEFAULT_MODEL_ORDER[1]): MPNet Multilingüe v2.
# Se usa como respaldo si el primario falla.
SBERT_MODEL_FALLBACK = "paraphrase-multilingual-mpnet-base-v2"

# Opción rápida para lotes grandes en CPU (NO es del notebook, da resultados
# cercanos pero no idénticos). Si quieres fidelidad 1:1 usa el primario.
SBERT_MODEL_FAST = "paraphrase-multilingual-MiniLM-L12-v2"

# Modelo activo por defecto en la app
SBERT_MODEL_NAME = SBERT_MODEL_PRIMARY

# --- Umbrales de decisión (notebook DEFAULT_UMBRAL_*) ---
UMBRAL_DECISION_FUNCIONES = 0.60   # DEFAULT_UMBRAL_DECISION_FUNCIONES
UMBRAL_DECISION_ESTUDIO = 0.70     # DEFAULT_UMBRAL_DECISION_REQUISITOS_ESTUDIO
UMBRAL_DECISION_COMP = 0.65        # DEFAULT_UMBRAL_DECISION_REQUISITOS_COMP (lab + comp)

# --- Pesos para el score final ponderado (notebook DEFAULT_WEIGHT_*) ---
WEIGHT_FUNCIONES = 0.80
WEIGHT_ESTUDIO = 0.20
WEIGHT_COMP_LAB = 0.00
WEIGHT_COMP_COMP = 0.00

# --- Preprocesamiento (notebook defaults) ---
MIN_WORDS_PER_ITEM = 2              # MIN_WORDS_PER_ITEM
ELIMINAR_DUPLICADOS = True          # elim_dups_box.value
NORMALIZAR_TEXTO = True             # norm_box.value
LEMATIZAR = False                   # lemma_box.value (requiere spaCy; OFF por defecto)
USAR_JACCARD = False                # usar_jacc_box.value
PESO_COSENO = 1.00                  # DEFAULT_PESO_COSENO
PESO_JACCARD = 0.00                 # DEFAULT_PESO_JACCARD

# --- Decisión ---
INCLUIR_REQUISITOS_EN_DECISION = True  # chk_incluir_requisitos.value

# --- Columnas esperadas en el Excel de entrada ---
# Mismas que valida el notebook en on_upload_change.
REQUIRED_COLUMNS = [
    "No. OPEC",
    "Código",
    "Denominación",
    "Grado",
    "Nivel Jerárquico",
    "Orden",
    "Naturaleza Jurídica",
    "Salario",
    "Requisitos Estudio",
    "Requisitos Experiencia",
    "Funciones",
    "Competencias Laborales",
    "Competencias Comportamentales",
    "modalidad",
    "nombre_entidad",
]

ID_COLUMN = "No. OPEC"

# --- Tolerancia salarial (notebook SALARY_DIFF_PERCENTAGE_THRESHOLD) ---
SALARY_DIFF_PERCENTAGE_THRESHOLD = 0.10  # 10%
