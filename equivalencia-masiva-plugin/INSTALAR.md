# Instalar el plugin Equivalencia Masiva en tu Claude Code

**Despacho III — Comisionado Edwin Arturo Ruiz Moreno · CNSC**

Esta guía está dirigida a los miembros del Despacho que quieran usar el análisis masivo de equivalencias **directamente desde Claude Code**, sin necesidad de abrir la app web Streamlit.

Una vez instalado este plugin, podrás decirle cosas así al Claude de tu máquina:

- *"Analízame este Excel: C:/Users/miuser/Desktop/opec_abril.xlsx"* → Claude corre el pipeline solo.
- *"Dame la plantilla vacía en mi escritorio"* → Claude genera el `.xlsx`.
- *"Revisa el par OPEC 221860 vs 152423"* → Claude da scores detallados.
- *"Revisa los 15 pares NO_EQUIVALENTES y dame tu segunda opinión"* → el subagente `equivalencia-validator` hace revisión rigurosa con marco jurídico CNSC.

Todo conversacional, todo en español, sin clicks.

---

## Requisitos previos

1. **Claude Code instalado** con soporte de plugins. Si no lo tienes, descárgalo desde [claude.ai/code](https://claude.ai/code).
2. **Python 3.11 o superior** instalado en Windows.
3. **Clon local del proyecto Equivalencia Masiva** (el plugin importa los módulos `core/` del proyecto).

---

## Paso 1 — Clona el proyecto completo

Si aún no tienes el proyecto Equivalencia Masiva en tu máquina:

```bash
cd C:/Users/TU_USUARIO/Downloads
git clone https://github.com/despacho-earm/equivalencia-masiva.git
```

O descárgalo como ZIP desde el repo del Despacho y descomprímelo en `C:/Users/TU_USUARIO/Downloads/listas de elejibles/`.

---

## Paso 2 — Instala dependencias de Python

Abre una terminal (PowerShell o CMD) en la carpeta del proyecto y corre:

```bash
cd "C:/Users/TU_USUARIO/Downloads/listas de elejibles"

pip install -r requirements.txt
pip install "mcp[cli]>=1.0"
```

Esto instala:
- Las dependencias del proyecto (`pandas`, `openpyxl`, `sentence-transformers`, `torch`, etc.)
- El SDK de MCP (necesario para que el servidor del plugin arranque)

**Nota**: la primera vez que uses el plugin, Python descargará el modelo SBERT `hiiamsid/sentence_similarity_spanish_es` (~450 MB). Esto sólo pasa una vez y queda cacheado en `~/.cache/huggingface/`.

---

## Paso 3 — Instala el plugin en tu Claude Code

En la misma terminal:

```bash
claude plugins install ./equivalencia-masiva-plugin
```

Claude Code registra el plugin con:
- ✅ 3 slash commands (`/analizar`, `/plantilla`, `/reporte`)
- ✅ 1 agente (`equivalencia-validator`)
- ✅ 1 skill (`flujo-equivalencia-earm`)
- ✅ 1 hook (validador automático de Excels OPEC)
- ✅ 1 servidor MCP con 7 tools

---

## Paso 4 — Verifica la instalación

Abre Claude Code en cualquier carpeta de trabajo y escribe:

```
/plantilla
```

Claude debería:

1. Invocar el tool `mcp__equivalencia-masiva-core__generar_plantilla`.
2. Generar `plantilla_equivalencia_masiva.xlsx` en tu directorio actual.
3. Confirmarte la ruta exacta del archivo.

Si todo funciona, ya puedes empezar a usarlo con archivos reales.

---

## Cómo usarlo en tu día a día

### Caso 1 — Análisis completo de un lote nuevo

```
/analizar C:/Users/miuser/Desktop/opec_abril.xlsx
```

Claude va a:

1. Validar que el Excel tenga las 15 columnas requeridas.
2. Previsualizar el agrupamiento (cuántos empleos base 4.0, cuántas listas candidatas).
3. Correr el pipeline SBERT completo (primera vez: 1-2 min descargando modelo).
4. Reportar totales (EQUIVALENTES vs NO_EQUIVALENTES) y las razones principales de rechazo.
5. Ofrecerte generar reporte Excel o PDF.

### Caso 2 — Revisión rigurosa de pares dudosos

Después de un análisis, si quieres segunda opinión:

```
Revisa los pares NO_EQUIVALENTES y dime cuáles realmente lo son y cuáles son borderline.
```

Claude invoca automáticamente el agente **`equivalencia-validator`**, que:

- Cita los umbrales violados con la distancia exacta al umbral.
- Distingue fallas duras (nivel distinto, grado distinto) de fallas borderline (score 1-5 puntos debajo del umbral).
- Cita el marco jurídico CNSC (Decreto 1083/2015, Ley 2418/2024).
- Recomienda revisión manual cuando sospecha falso negativo del modelo SBERT.

### Caso 3 — Sólo descargar plantilla vacía

```
/plantilla C:/Users/miuser/Desktop/mi_plantilla.xlsx
```

Genera el archivo en la ruta que indiques con las 15 columnas + 3 filas de ejemplo + tooltips.

### Caso 4 — Generar reportes de un análisis previo

```
/reporte C:/Users/miuser/Desktop/opec_abril.xlsx --ambos
```

Corre análisis y genera Excel consolidado + PDF detallado, ambos con el diseño corporativo del Despacho.

### Caso 5 — Análisis de un par específico sin todo el lote

Simplemente pídelo en lenguaje natural:

```
Dame el análisis detallado del par: empleo base OPEC 221860 contra lista OPEC 152423, del Excel opec_abril.xlsx.
```

Claude usa `mcp__equivalencia-masiva-core__analizar_par` y te da todos los scores por aspecto.

---

## Hook automático — validación silenciosa de Excels

Cualquier archivo `.xlsx` que tú (o Claude) guardes con "opec", "equivalencia", "elegibles" o "empleo" en el nombre, va a pasar por el hook automático.

- Si tiene las 15 columnas → mensaje verde silencioso (no interrumpe).
- Si le faltan columnas → te alerta diciendo cuáles faltan y sugiere usar `/plantilla`.

Esto previene que trabajes durante media hora con un Excel mal formateado y lo descubras sólo al correr el análisis.

---

## Actualizar el plugin

Si el Despacho publica una nueva versión (ej: umbrales ajustados, nuevas columnas, mejor reporte PDF):

```bash
cd "C:/Users/TU_USUARIO/Downloads/listas de elejibles"
git pull
claude plugins reload equivalencia-masiva
```

---

## Desinstalar

```bash
claude plugins uninstall equivalencia-masiva
```

El código fuente queda en tu disco — sólo se desregistra del Claude Code.

---

## Problemas frecuentes

### "No se encuentra el comando `claude`"

Claude Code no está en tu PATH. Abre la aplicación Claude Code manualmente o agrega su binario al PATH del sistema.

### "MCP server failed to start"

Es porque Python o el paquete `mcp[cli]` no están instalados correctamente. Ejecuta:

```bash
python -c "import mcp; print(mcp.__version__)"
```

Debe imprimir una versión. Si da error, corre:

```bash
pip install "mcp[cli]>=1.0"
```

### "Module 'core' not found" cuando corro /analizar

El MCP server no está encontrando los módulos del proyecto padre. Verifica:

1. La carpeta del plugin está DENTRO del proyecto: `listas de elejibles/equivalencia-masiva-plugin/`.
2. No cambiaste el `.mcp.json` del plugin (el PYTHONPATH depende de `${CLAUDE_PLUGIN_ROOT}/..`).

### "La primera corrida tarda muchísimo"

Normal. La primera vez el modelo SBERT se descarga (~450 MB). Las siguientes corridas en la misma sesión son mucho más rápidas porque el modelo queda en memoria.

### "Quiero usar el modelo rápido (MiniLM) en vez del STS Spanish"

Edita `config.py` del proyecto padre y cambia `SBERT_MODEL_NAME = SBERT_MODEL_PRIMARY` a `SBERT_MODEL_NAME = SBERT_MODEL_FAST`. Reinicia Claude Code.

---

## Soporte

Para reportar bugs o sugerir mejoras: `despacho.earm@cnsc.gov.co`
