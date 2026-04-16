---
description: Genera reporte Excel consolidado y/o PDF detallado del análisis masivo
argument-hint: ruta/al/archivo.xlsx [--pdf|--excel|--ambos] (default --ambos)
allowed-tools: ["Bash", "mcp__equivalencia-masiva-core__analizar_masivo", "mcp__equivalencia-masiva-core__generar_reporte_excel", "mcp__equivalencia-masiva-core__generar_reporte_pdf"]
---

# /reporte — Generar reporte del análisis

Ejecuta el análisis masivo (o reutiliza uno previo) y exporta los resultados
como Excel consolidado (una fila por par con 46+ columnas) y/o PDF detallado
(portada + resumen ejecutivo + detalle por grupo + detalle por par).

## Instrucciones para Claude

El argumento `$ARGUMENTS` contiene:
- Una ruta a Excel (.xlsx) — obligatorio
- Flags opcionales: `--pdf`, `--excel`, `--ambos` (default: `--ambos`)

### Paso 1 — Ejecutar análisis

Llama a `mcp__equivalencia-masiva-core__analizar_masivo(ruta_excel=...)` para
obtener el `run_id` y filas cacheadas.

Si el análisis tarda, adviértele al usuario que la primera vez el modelo SBERT
se descarga (~450 MB, 1-2 min).

### Paso 2 — Generar reportes según el flag

Según los flags detectados en `$ARGUMENTS`:

**`--excel` o `--ambos`**:
```
mcp__equivalencia-masiva-core__generar_reporte_excel(
    run_id=<del paso 1>,
    ruta_salida=<cwd>/Equivalencia_Masiva_<run_id>.xlsx
)
```

**`--pdf` o `--ambos`**:
```
mcp__equivalencia-masiva-core__generar_reporte_pdf(
    run_id=<del paso 1>,
    ruta_salida=<cwd>/Equivalencia_Masiva_<run_id>.pdf
)
```

### Paso 3 — Reportar al usuario

- Ruta(s) exacta(s) de los archivos generados
- Tamaño de cada uno
- Resumen mínimo del análisis: X EQUIVALENTES, Y NO_EQUIVALENTES de Z pares totales
- Ofrecer abrir los archivos con `start` / `open` / `xdg-open`

### Contenido de cada reporte

**Excel consolidado**:
- 1 fila por cada par (base 4.0 ↔ lista)
- 46+ columnas: identificación, veredicto, score ponderado, razones,
  coberturas SBERT por aspecto, gating nivel/salario, textos originales
  para auditoría, modelo usado
- Colores condicionales por veredicto (verde/rojo)
- Pestaña "Resumen" con totales por clasificación

**PDF detallado**:
- Portada con fecha, archivo analizado, metadata del Despacho
- Resumen ejecutivo con tabla de totales y desglose por entidad
- Por cada grupo: encabezado, tabla-resumen, detalle por par con
  scores SBERT, tabla pasa/no-pasa por aspecto, decisión final
- Razones de no equivalencia y jerarquía de experiencia explicadas
