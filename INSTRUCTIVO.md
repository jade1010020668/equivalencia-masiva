# 📘 Instructivo de Uso — Equivalencia Masiva

**Despacho III · Comisionado Edwin Arturo Ruiz Moreno · CNSC**

Esta guía explica paso a paso cómo usar la aplicación **Equivalencia Masiva** para analizar listas de elegibles de forma automatizada. No requiere conocimientos técnicos.

---

## ¿Qué es esta herramienta?

Es una aplicación web que reemplaza el flujo manual de revisar lista por lista con el notebook de Colab. En lugar de:

1. Abrir `criterio base` → subir Excel → agrupar → descargar ZIP.
2. Abrir `mismo_grado.ipynb` en Colab → subir cada Excel → seleccionar base → analizar → exportar → repetir para cada base.

Con esta app haces **un solo paso**:

> Subir el Excel completo → click en "Ejecutar análisis" → descargar Excel consolidado + PDF con todos los análisis.

Los resultados son **idénticos** a los del notebook (usa el mismo modelo SBERT, los mismos umbrales, la misma lógica de decisión).

---

## Paso 1 — Preparar el Excel de entrada

### Opción A: Usar la plantilla que te da la app

1. Abre la aplicación en tu navegador.
2. En la sección **"0. Descargar plantilla"**, click en **📄 Descargar plantilla .xlsx**.
3. Abre el archivo en Excel. Tiene:
   - **Pestaña 1 (OPEC)**: los 15 encabezados que la app espera, con tooltips en cada celda explicando qué poner.
   - **Pestaña 2 (Instrucciones)**: documentación de cada columna y notas importantes.
   - **3 filas de ejemplo** (OPEC 999001-999003) que puedes borrar antes de cargar tus datos reales.

### Opción B: Usar un Excel que ya tengas

Si ya tienes el Excel del pipeline CNSC con los 15 encabezados, puedes usarlo directamente. La app valida que tenga todas las columnas requeridas y te avisa si falta alguna.

### Columnas requeridas

| Columna | Qué va aquí |
|---|---|
| `No. OPEC` | Número único de la Oferta Pública (identificador del empleo). |
| `Código` | Código del cargo en el manual de funciones. |
| `Denominación` | Nombre del cargo (ej: "Profesional Universitario"). |
| `Grado` | Grado del empleo (número entero). |
| `Nivel Jerárquico` | Directivo / Asesor / Profesional / Técnico / Asistencial. |
| `Orden` | Nacional / Territorial. |
| `Naturaleza Jurídica` | Ministerio / Municipio / Departamento / etc. |
| `Salario` | Salario mensual en pesos (sólo números). |
| `Requisitos Estudio` | Texto del manual de funciones. |
| `Requisitos Experiencia` | Texto del manual de funciones. |
| `Funciones` | Texto con viñetas o saltos de línea. |
| `Competencias Laborales` | Texto con viñetas o saltos de línea. |
| `Competencias Comportamentales` | Texto con viñetas o saltos de línea. |
| `modalidad` | **"4.0"** para empleo base vigente, **"LISTAS"** para cada lista candidata. |
| `nombre_entidad` | Nombre de la entidad titular del empleo. |

### Reglas de agrupamiento

La app agrupa automáticamente cada empleo base 4.0 con sus listas candidatas siguiendo estas reglas (las mismas que la app React `criterio base`):

- Las listas de elegibles (`modalidad=LISTAS`) se agrupan con el empleo base 4.0 (`modalidad=4.0`) **del mismo** `nombre_entidad`, `Nivel Jerárquico` y `Grado`.
- Si un empleo base 4.0 no tiene listas del mismo grado, aparece como "base huérfana" (se incluye en el reporte pero sin pares para analizar).

---

## Paso 2 — Cargar el Excel en la app

1. En la sección **"1. Cargar Excel de OPEC"**, haz click en **"Browse files"** o arrastra el archivo.
2. La app valida las columnas y muestra:
   - **Filas leídas** (total de registros en el Excel).
   - **Grupos (bases 4.0)** generados.
   - **Pares (base, lista)** a analizar.
   - **Bases sin listas** (huérfanas).
3. Abre **"Previsualización del Excel"** para confirmar visualmente que se cargó correctamente.

Si falta alguna columna, la app te muestra la lista de faltantes y detiene el proceso.

---

## Paso 3 — Configurar el análisis (opcional)

En **"2. Configuración del análisis"** puedes ajustar:

### Modelo semántico

- **STS Spanish** (default, recomendado): replica exactamente el notebook de Colab. ~450 MB, ~1-3 segundos por par en CPU.
- **MPNet Multilingüe**: segunda opción del notebook. ~500 MB, similar velocidad.
- **MiniLM Multilingüe** (rápido): ~4x más veloz, resultados muy cercanos pero NO idénticos al notebook. Úsalo sólo si tienes un lote muy grande y prefieres velocidad.

### Incluir Requisitos en la decisión

- **Activo** (default del notebook): la decisión exige que Funciones + Estudio + Comp. Laborales + Comp. Comportamentales pasen SUS umbrales.
- **Inactivo**: solo Funciones + Nivel + Salario importan.

### Umbrales

Vienen con los valores default del notebook. Puedes subirlos para ser más estricto o bajarlos para rescatar más casos.

### Pesos del score ponderado

Controlan cómo se calcula el "Score Ponderado" final (columna del reporte). Los defaults son 0.80 Funciones + 0.20 Estudio, igual que el notebook.

---

## Paso 4 — Ejecutar el análisis masivo

1. Click en **"▶️ Ejecutar análisis masivo"**.
2. La **primera vez** que usas la app, descarga el modelo SBERT (~450 MB). Esto tarda 1-2 minutos con buena conexión y luego queda cacheado.
3. La app pre-computa embeddings de todos los textos únicos de tu Excel (optimización) y luego procesa cada par.
4. La barra de progreso muestra:
   - Grupo actual.
   - Pares analizados / totales.
   - Tiempo transcurrido y ETA.

**Tiempos típicos en CPU** (Windows 10 sin GPU):

| Pares a analizar | Tiempo aproximado |
|---|---|
| 50 | 2-5 minutos |
| 200 | 8-15 minutos |
| 500 | 20-40 minutos |
| 1000 | 40-90 minutos |

Si tu PC tiene GPU NVIDIA con CUDA, los tiempos son ~10x menores.

---

## Paso 5 — Descargar los resultados

Al terminar, la sección **"4. Resultados"** muestra:

- **Métricas**: cantidad de pares EQUIVALENTES vs NO EQUIVALENTES.
- **Descargar Excel consolidado**: archivo `.xlsx` con 1 fila por par y 46+ columnas de análisis. Úsalo para filtrar, pivotar y exportar a otros sistemas.
- **Generar informe PDF detallado**: genera (bajo demanda, puede tardar unos segundos) un PDF profesional con portada, resumen ejecutivo, desglose por grupo y detalle por par.
- **Tabla en pantalla**: visualización rápida con filtro "mostrar solo EQUIVALENTES".

### Qué contiene el Excel consolidado

Una fila por cada par `(base 4.0, lista)` con:

- Identificación del par (entidad, grupo, OPEC de ambos, denominación, grado, nivel, salario).
- **Decisión final** (EQUIVALENTE / NO_EQUIVALENTE) con color de fondo.
- **Score ponderado** final.
- **Razones de no equivalencia** (explicación de por qué no pasó).
- Coberturas SBERT de los 5 aspectos (Funciones, Estudio, Comp Lab, Comp Comp, Experiencia).
- Banderas de Pasa/No Pasa por cada aspecto.
- Tipo de experiencia detectado en base y lista + mensaje de jerarquía.
- Modelo SBERT usado.
- Textos originales para auditoría.

### Qué contiene el PDF detallado

- **Portada** con fecha, nombre del archivo y metadatos del Despacho.
- **Resumen ejecutivo** con totales y desglose por entidad.
- **Por cada grupo** (un empleo base 4.0 con sus listas candidatas):
  - Encabezado con datos del grupo.
  - Tabla-resumen con todas las listas del grupo y su clasificación.
  - **Detalle por par**: identificación lado a lado, tabla de scores SBERT con umbrales y pasa/no-pasa, decisión final con color, razones.

El PDF es un informe listo para anexar a un oficio.

---

## Paso 6 — Interpretar los resultados

### "Decisión Final: EQUIVALENTE"

Significa que el par cumple **todas** estas condiciones:

1. Mismo Nivel Jerárquico.
2. Mismo Grado y salarios equivalentes (≤10% diferencia).
3. Cobertura SBERT Funciones ≥ umbral.
4. Si "Incluir Requisitos" está activo:
   - Cobertura SBERT Estudio ≥ umbral.
   - Cobertura SBERT Comp. Laborales ≥ umbral.
   - Cobertura SBERT Comp. Comportamentales ≥ umbral.

Estos pares son candidatos para usar la lista como reemplazo del empleo base, **sujetos a revisión jurídica final del Despacho**.

### "Decisión Final: NO_EQUIVALENTE"

Falló al menos una de las condiciones anteriores. La columna **"Razones No Equivalencia"** explica cuál.

### Score ponderado

Es un número entre 0% y 100% que combina los scores SBERT con los pesos definidos. Sirve para priorizar revisión: **los pares con mayor score son los más "prometedores"** aunque hayan sido clasificados como NO_EQUIVALENTE (pueden ser casos borderline donde una revisión manual podría aprobarlos).

---

## Preguntas frecuentes

### ¿Puedo confiar en la decisión automática sin revisarla?

**No**. La app automatiza la evaluación semántica que antes hacías manualmente con el notebook, pero la **decisión final legal siempre es del Despacho**. Usa los resultados como pre-filtro para concentrar tu revisión en los pares más prometedores.

### ¿Por qué un par sale NO_EQUIVALENTE aunque las funciones son casi iguales?

Posiblemente falló en otro aspecto: Estudio, Comp Laborales, Comp Comportamentales, Nivel o Salario. Revisa la columna **"Razones No Equivalencia"** del Excel para ver cuál fue el problema.

### ¿Puedo ajustar los umbrales para ser más permisivo?

Sí, en la sección de Configuración. **Pero ten en cuenta**: bajar los umbrales puede hacer que la app apruebe pares que el notebook original hubiera rechazado con los defaults. Usa umbrales custom con responsabilidad.

### ¿Qué pasa si mi Excel no tiene Competencias Laborales o Comportamentales?

El notebook (y esta app) lo maneja así: si los textos están vacíos en ambos lados (base y lista), el aspecto pasa automáticamente (cobertura = 1.0). Si están vacíos en uno solo, el aspecto NO pasa.

Si quieres que la app ignore las competencias completamente, desactiva "Incluir Requisitos" en la configuración.

### ¿Los resultados son reproducibles?

Sí. Para el mismo Excel con los mismos umbrales y el mismo modelo, los resultados son **idénticos entre corridas** (SBERT es determinista).

---

## Soporte

Para reportar bugs o sugerir mejoras, contacta al equipo técnico del Despacho III del Comisionado Edwin Arturo Ruiz Moreno.
