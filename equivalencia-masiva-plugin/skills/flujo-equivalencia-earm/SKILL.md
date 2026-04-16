---
name: flujo-equivalencia-earm
description: |
  Flujo institucional del Despacho III EARM (CNSC) para analizar masivamente
  listas de elegibles contra empleos base 4.0. Define preprocesamiento,
  umbrales de cobertura, compuerta AND, jerarquía de experiencia y formato
  de reportes. Usar SIEMPRE que el usuario mencione cualquiera de estos
  términos: OPEC, listas de elegibles, equivalencia de empleos, empleo
  base 4.0, criterio base, mismo grado, análisis masivo CNSC, Despacho EARM,
  Comisionado Ruiz Moreno, `mismo_grado_.ipynb`, o pida generar plantilla
  o reporte de equivalencias.
---

## Flujo estándar del Despacho III EARM — análisis masivo de equivalencia de empleos

Este skill define el proceso de revisión que sigue el Despacho del Comisionado
Edwin Arturo Ruiz Moreno para autorizar el uso de listas de elegibles (OPEC X) para
cubrir vacantes de empleos base vigentes (OPEC Y). El flujo es un **port fiel**
del notebook `mismo_grado_.ipynb` que el Despacho venía usando manualmente en
Google Colab, automatizado para procesar lotes completos en una sola corrida.

### Paso 1 — Ingesta del Excel

El Excel de entrada debe tener estas 15 columnas:

```
No. OPEC, Código, Denominación, Grado, Nivel Jerárquico,
Orden, Naturaleza Jurídica, Salario, Requisitos Estudio,
Requisitos Experiencia, Funciones, Competencias Laborales,
Competencias Comportamentales, modalidad, nombre_entidad
```

Cada fila es un empleo. El campo `modalidad` distingue:
- `4.0` → empleo base vigente (se está buscando cubrir con listas)
- `LISTAS` → lista de elegibles candidata

### Paso 2 — Agrupamiento

Portado de `core/grouping.py` (original: `copy-of-criterio-base.zip::services/excelProcessor.ts`).

Por cada combinación `(nombre_entidad, Nivel Jerárquico)`:
1. Separar filas modalidad `4.0` de las de modalidad `LISTAS`.
2. Para cada empleo base 4.0, filtrar las listas que tienen el **mismo Grado**.
3. Generar nombre de grupo: `{Entidad} - {Inicial Nivel} - B - {OPEC base}`.
   - Inicial Nivel: A (Asistencial), T (Técnico), P (Profesional), etc.
4. Si un empleo base 4.0 no tiene ninguna lista del mismo grado → marcar como "huérfano"
   (se reporta pero no genera pares para analizar).

### Paso 3 — Análisis por par (base 4.0, lista candidata)

Por cada par se calculan **7 métricas** en `core/semantic.py` (port de
`mismo_grado_.ipynb`):

| Métrica | Cómo se calcula | Umbral default |
|---|---|---|
| Funciones (cobertura SBERT) | `cobertura_prom_max_1(matriz_cos)` sobre items con `procesar_bloque` | ≥ 0.60 |
| Requisitos Estudio | Misma función con `preprocesar_educacion` aplicado | ≥ 0.70 |
| Competencias Laborales | Misma función | ≥ 0.65 |
| Competencias Comportamentales | Misma función | ≥ 0.65 |
| Experiencia | Hierarchy check + cobertura del texto limpio | informativo |
| Nivel Jerárquico | Igualdad exacta normalizada | debe pasar |
| Salario/Grado | Mismo grado + diferencia ≤ 10% | debe pasar |

**Modelo SBERT**: `hiiamsid/sentence_similarity_spanish_es` (STS Spanish, ~450 MB).
Es el modelo por defecto del notebook. Para lotes grandes en CPU se puede usar
`paraphrase-multilingual-MiniLM-L12-v2` (más rápido pero resultados ligeramente
distintos).

**Métrica clave**: `cobertura_prom_max_1 = mean(max(matriz_coseno, axis=1))`.
Es decir: para cada ítem del empleo base, buscar el mejor match en la lista,
promediar. Esto mide si "todo lo que pide el base está cubierto por la lista".

### Paso 4 — Decisión (compuerta AND estricta)

Portado de `core/decision.py` (original: `on_analizar_click` del notebook):

```python
es_equivalente = (
    nivel.pasa
    AND salario.pasa
    AND cobertura_funciones >= umbral_funciones
)
if incluir_requisitos:  # default: True
    es_equivalente AND= (
        cobertura_estudio >= umbral_estudio
        AND cobertura_comp_lab >= umbral_comp
        AND cobertura_comp_comp >= umbral_comp
    )
```

**Score ponderado final** (para ordenamiento y desempate):

```python
score = (
    funciones * 0.80
    + estudio * 0.20
    + comp_lab * 0.00
    + comp_comp * 0.00
) / (0.80 + 0.20 + 0.00 + 0.00)
```

(Los pesos de competencias son 0 por diseño del notebook — sólo sirven para
gatear, no para el score).

### Paso 5 — Jerarquía de experiencia

`HIERARQUIA_EXPERIENCIA` define qué tipos de experiencia satisfacen a otros:

```
PROFESIONAL_RELACIONADA → {PROFESIONAL_RELACIONADA, PROFESIONAL, LABORAL_RELACIONADA, LABORAL}
PROFESIONAL            → {PROFESIONAL, LABORAL}
LABORAL_RELACIONADA    → {LABORAL_RELACIONADA, LABORAL}
DOCENTE                → {DOCENTE, PROFESIONAL, LABORAL}
LABORAL                → {LABORAL}
NO_IDENTIFICADO        → {NO_IDENTIFICADO}  (no satisface a ningún otro)
```

Si el tipo del base está en la jerarquía del tipo de la lista → la experiencia
del base "cubre" el requisito de la lista.

### Paso 6 — Reportes

**Excel consolidado** (`core/report.py`):
- Una fila por cada par (base, lista)
- 46+ columnas: identificación + veredicto + scores por aspecto + razones + gating + textos originales + modelo usado
- Colores condicionales por veredicto (verde/rojo)
- Pestaña "Resumen" con totales

**PDF detallado** (`core/pdf_report.py`):
- Portada institucional (Despacho EARM, fecha, archivo, metadatos)
- Resumen ejecutivo (tabla de totales + desglose por entidad)
- Por cada grupo: encabezado, tabla-resumen de listas, detalle por par
- Detalle por par: tabla identificación, tabla scores SBERT con umbrales, decisión final con color, razones

### Terminología obligatoria del Despacho

| Prefiere | Evita |
|---|---|
| "empleo base vigente" | "empleo fuente", "empleo origen" |
| "lista de elegibles candidata" | "lista destino", "elegibles target" |
| "veredicto" | "clasificación", "resultado", "decision" |
| "cobertura semántica" | "similarity score", "score SBERT" (sólo en datos técnicos) |
| "compuerta AND" | "gate AND", "lógica AND" |
| "empleo base 4.0" | "vacante 4.0", "plaza 4.0" |
| "OPEC" | "oferta", "vacante OPEC" |

### Casos borde importantes

- **Textos vacíos**: si AMBOS lados tienen el aspecto vacío (ej: ni base ni lista
  definen Competencias Laborales), el aspecto **pasa trivialmente** con cobertura 1.0
  (replica `eval_crit` del notebook). Si sólo UNO está vacío, falla.
- **Bases huérfanas**: empleos base 4.0 sin listas del mismo grado se incluyen en
  el reporte pero con 0 pares — no se pueden cubrir con el Excel dado.
- **Múltiples bases mismo grupo**: si hay varias filas 4.0 con misma entidad+nivel,
  cada una genera su propio grupo con sufijo `(1)`, `(2)`, etc.

### Archivos clave del proyecto

- `core/grouping.py` — agrupamiento (port del React)
- `core/semantic.py` — motor SBERT (port del notebook)
- `core/decision.py` — compuerta AND (port del notebook)
- `core/report.py` — Excel consolidado
- `core/pdf_report.py` — PDF detallado
- `core/template.py` — generador de plantilla vacía
- `config.py` — umbrales y constantes centralizadas
- `app.py` — Streamlit UI (interfaz web con diseño EARM)

### Cuando aplicar este skill

El Claude del Despacho debe aplicar este skill automáticamente cuando el usuario
pida cualquiera de estas cosas:

- "Analiza este Excel de OPEC"
- "Revisa si estas listas son equivalentes al empleo 4.0"
- "Genera el reporte de equivalencias"
- "Descarga la plantilla de OPEC"
- "Dame los scores SBERT de este par"
- "Revisa la jerarquía de experiencia entre estos dos OPEC"
- "¿Qué listas puedo usar para cubrir el empleo 221860?"
