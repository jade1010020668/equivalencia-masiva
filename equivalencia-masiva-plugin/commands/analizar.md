---
description: Analiza masivamente un Excel de OPEC con empleos base 4.0 y listas de elegibles
argument-hint: ruta/al/archivo.xlsx [--limite N] [--sin-requisitos]
allowed-tools: ["Read", "Bash", "mcp__equivalencia-masiva-core__validar_columnas", "mcp__equivalencia-masiva-core__agrupar_excel", "mcp__equivalencia-masiva-core__analizar_masivo", "mcp__equivalencia-masiva-core__generar_reporte_excel", "mcp__equivalencia-masiva-core__generar_reporte_pdf"]
---

# /analizar — Análisis masivo de equivalencia de empleos

Ejecuta el pipeline completo del Despacho III EARM (CNSC) sobre un Excel de OPEC:
agrupamiento por entidad/nivel/grado, análisis semántico SBERT sobre 5 aspectos,
y decisión final con compuerta AND (mismo criterio que `mismo_grado_.ipynb`).

## Instrucciones para Claude

El usuario pidió analizar un Excel de OPEC con listas de elegibles. El argumento
`$ARGUMENTS` puede contener:

- Una ruta de archivo `.xlsx` (obligatorio)
- Opcionalmente `--limite N` para sólo procesar los primeros N pares (smoke test)
- Opcionalmente `--sin-requisitos` para NO gatear por estudio/competencias (sólo
  funciones y nivel/salario importan — menos estricto)

### Paso 1 — Validar columnas

Llama a `mcp__equivalencia-masiva-core__validar_columnas(ruta_excel=...)`.

Si `ok: false`, muestra al usuario las columnas faltantes y detente. Indícale que
puede usar `/plantilla` para descargar el formato correcto.

### Paso 2 — Previsualizar agrupamiento (opcional si el archivo es grande)

Si el Excel tiene > 200 filas, llama primero a
`mcp__equivalencia-masiva-core__agrupar_excel(ruta_excel=...)` y muéstrale al usuario:
- Total de grupos (empleos base 4.0)
- Total de pares (base ↔ lista) a analizar
- Bases huérfanas (si hay)

Preguntarle si quiere continuar antes de gastar tiempo en SBERT.

### Paso 3 — Ejecutar análisis masivo

Llama a `mcp__equivalencia-masiva-core__analizar_masivo(ruta_excel=...)` con los
umbrales default del notebook (0.60/0.70/0.65) salvo que el usuario los cambie
explícitamente.

**IMPORTANTE**: la primera vez tarda 1-2 minutos (descarga del modelo SBERT
`hiiamsid/sentence_similarity_spanish_es`, ~450 MB). Adviértele al usuario.

### Paso 4 — Reportar resultados

Al usuario en español, con terminología CNSC:

1. **Resumen ejecutivo**:
   - Total de pares analizados
   - Cuántos EQUIVALENTES y cuántos NO_EQUIVALENTES (con porcentajes)
   - Cantidad de grupos
2. **Top 5 grupos con más EQUIVALENTES**: "Estos son los casos donde las listas
   están mejor alineadas con el empleo base vigente — candidatos fuertes."
3. **Top 5 pares NO_EQUIVALENTES con score alto** (>= 0.55 score ponderado):
   "Estos son borderline. Recomiendo revisión manual antes de descartarlos."
4. **Razones recurrentes de no-equivalencia**: agrupa por razón principal
   ("Nivel diferente", "Funciones < 60%", "Estudio < 70%", etc.).

### Paso 5 — Ofrecer reportes

Guarda el `run_id` del resultado y ofrece al usuario:
- "¿Quieres el Excel consolidado? (usa `/reporte $ARGUMENTS --excel`)"
- "¿O el PDF detallado? (`/reporte $ARGUMENTS --pdf`)"
- "¿O ambos? (`/reporte $ARGUMENTS --ambos`)"

## Terminología del Despacho

Usa siempre:
- "empleo base vigente" (modalidad 4.0)
- "lista de elegibles candidata" (modalidad LISTAS)
- "veredicto" (no "clasificación" ni "resultado")
- "cobertura semántica" (no "similarity score")
- "compuerta AND" al explicar la decisión
