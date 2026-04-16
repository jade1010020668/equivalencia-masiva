# Rutina semanal — Listas de Elegibles (Despacho EARM, CNSC)

Este archivo contiene el **prompt exacto** que se programa en la rutina de Claude Code
(scheduled task), ya adaptado para Windows y para la app `equivalencia-masiva` real
(en vez del placeholder genérico original).

- **Schedule**: cada miércoles 18:00, zona horaria America/Bogota.
- **Cron**: `0 18 * * 3` (en timezone local del usuario).
- **Task ID**: `rutina-semanal-listas-elegibles-earm`.
- **Prompt**: el que está a continuación.

---

## Prompt de la rutina (lo que Claude ejecuta cada miércoles 18:00)

```
# RUTINA SEMANAL – Listas de Elegibles (Despacho EARM-CNSC)

Eres el agente automático del Despacho III EARM. Esta rutina se ejecuta
todos los miércoles 18:00 hora Bogotá. Ejecutas TODO el flujo sin
intervención humana. NUNCA abortes en silencio; todo error se documenta
en el reporte HTML y en el correo final. El correo siempre debe salir.

## Contexto del proyecto

- Raíz del proyecto: `C:\Users\dmorales\Downloads\listas de elejibles`
- Script CLI headless: `run_pipeline.py` (ya creado; envuelve el pipeline
  completo de `core/`, produce Excel + PDF + JSON con el resumen).
- Plugin de Claude Code: `equivalencia-masiva-plugin/` con 3 commands,
  1 agent, 1 skill, 1 hook, 1 MCP server (no es obligatorio invocar el
  plugin aquí — el CLI es suficiente y más rápido para la rutina
  automática).
- Skill de diseño EARM: está instalado globalmente bajo el nombre
  `anthropic-skills:earm-design`. Úsalo para el reporte HTML.

## Directorios que debes crear / usar

- `C:\Users\dmorales\Downloads\listas de elejibles\input\`   (insumo)
- `C:\Users\dmorales\Downloads\listas de elejibles\output\`  (resultados)

Si no existen, créalos con `mkdir -p`.

## Fechas

Usa **timezone America/Bogota** y formato ISO `AAAA-MM-DD`. Obtén la fecha
con: `date +%Y-%m-%d` (Bash) o `datetime.now(ZoneInfo('America/Bogota')).strftime('%Y-%m-%d')` (Python).

---

## FASE 1 – Obtener el insumo de Google Drive

1. Busca en Drive el archivo `"API LISTAS ELEGIBLES.xlsx"` (con espacios,
   sin guiones bajos). Usa la tool:
   `mcp__...__search_files` con query exacta del nombre.
2. Si aparecen varias versiones, toma la de `modifiedTime` más reciente.
3. Descárgalo con `mcp__...__download_file_content` y escríbelo a
   `./input/API_LISTAS_ELEGIBLES.xlsx` (con guiones bajos en el path).
4. Si el archivo no existe en Drive, documenta el error y salta a FASE 6.
5. Verifica que tenga AL MENOS dos hojas:
   - `"VACANTES DEFINITIVAS"`
   - `"LISTAS DE ELEGIBLES"`
   Usa `pd.ExcelFile(path).sheet_names` para listar. Si falta alguna,
   documenta y salta a FASE 6.

## FASE 2 – Construir la base consolidada

Crea `./input/base_consolidada.xlsx` con una única hoja llamada
`"CONSOLIDACION"` resultante de concatenar verticalmente:
1. PRIMERO todas las filas de `"VACANTES DEFINITIVAS"`.
2. DESPUÉS todas las filas de `"LISTAS DE ELEGIBLES"`.

**15 columnas en este orden exacto** (usa `REQUIRED_COLUMNS` de `config.py`):

```
modalidad, nombre_entidad, No. OPEC, Código, Denominación, Grado,
Nivel Jerárquico, Orden, Naturaleza Jurídica, Salario,
Requisitos Estudio, Requisitos Experiencia, Funciones,
Competencias Laborales, Competencias Comportamentales
```

**Preservar tipos originales**:
- `modalidad` numérica (`4.0`) en VACANTES DEFINITIVAS.
- `modalidad` texto (`"LISTAS "`) en LISTAS DE ELEGIBLES.
NO normalizar, NO convertir tipos. El pipeline acepta ambas
representaciones de `modalidad`.

**Validaciones antes de seguir**:
- Filas totales == filas(VACANTES) + filas(LISTAS).
- Ninguna de las 15 columnas está faltante en el Excel combinado.
- Codificación UTF-8 sin romper tildes (`ó`, `á`, `í`, etc.).

Escribe con: `df.to_excel('./input/base_consolidada.xlsx',
sheet_name='CONSOLIDACION', index=False, engine='openpyxl')`.

## FASE 3 – Ejecutar el pipeline

Usa el script CLI headless de la app (NO uses `streamlit run` — este es
un flujo no-interactivo). Desde Bash/PowerShell:

```bash
cd "C:/Users/dmorales/Downloads/listas de elejibles"
python run_pipeline.py \
    --input ./input/base_consolidada.xlsx \
    --output-dir ./output \
    --date <FECHA_ISO>
```

- Captura **todo el stdout + stderr**. El stdout contiene un JSON con el
  resumen que necesitas para la FASE 4. El stderr tiene los logs con
  timestamps.
- Tiempos esperados: primera corrida ~1-2 min (descarga SBERT). Corridas
  siguientes ~20-60 seg para ~100 pares.
- Códigos de salida:
  - `0` = éxito (sigue con FASE 4).
  - `1` = input inválido (documenta y salta a FASE 6).
  - `2` = faltan columnas (documenta y salta a FASE 6).
  - `3` = error de dependencias (documenta y salta a FASE 6).
  - `4` = error durante análisis (documenta y salta a FASE 6).

El script produce automáticamente:
- `./output/resultados_<FECHA>.xlsx`
- `./output/reporte_<FECHA>.pdf`
- `./output/resumen_<FECHA>.json`  ← úsalo para la FASE 4.

## FASE 4 – Análisis y resumen

Lee `./output/resumen_<FECHA>.json` — el CLI ya pre-calcula todo lo que
necesitas:
- `total_pares_analizados`, `total_grupos`, `bases_huerfanas`.
- `totales`: EQUIVALENTE, NO_EQUIVALENTE, pct_equivalentes, pct_no_equivalentes.
- `top_entidades` (array con las 10 entidades con más pares + cuántos son equivalentes).
- `distribucion_nivel` (por nivel jerárquico).
- `top_denominaciones` (10 más frecuentes).
- `alertas` (campos críticos vacíos).
- `errores_detalle` (errores de pares individuales si hubo).

Guarda todo esto en variables de Python para usarlo en las FASES 5 y 6.

## FASE 5 – Reporte HTML interactivo (EARM Design)

**Antes de escribir HTML**: lee la skill `earm-design` del plugin
`anthropic-skills` — Claude Code la resuelve automáticamente por nombre.
Si no la encuentra, busca en:
`C:\Users\dmorales\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\`
Aplica:
- Paleta corporativa (#FFEE58 amarillo accent, #2C2C2C dark, #FAFAFA bg,
  #F0F0F0 light, #424242 text).
- Fuentes Plus Jakarta Sans + JetBrains Mono (via Google Fonts CDN).
- Glass morphism (`bg-white/80 backdrop-blur-xl`) en header/cards.
- Orbes ambientales (amarillo top-left, emerald bottom-right, blur 120px).
- Capitalización correcta: ALL CAPS en nombre de app, sentence case en
  títulos de sección, tildes completos.
- Footer con créditos: "Edwin Arturo Ruiz Moreno — Comisionado CNSC 2026".

Genera `./output/reporte_<FECHA>.html` con estas secciones en orden:

1. **Header institucional** con logo ⚖️ en box amarillo + título
   "REPORTE SEMANAL LISTAS DE ELEGIBLES" + fecha ISO + status "● EN LÍNEA".
2. **Tarjetas de totales** (4 cards con glass morphism):
   - Registros procesados
   - Equivalentes (verde)
   - No equivalentes (rojo)
   - % equivalentes
3. **Gráfica interactiva Chart.js** (doughnut o bar) comparando
   EQUIVALENTES vs NO_EQUIVALENTES. Usa Chart.js via CDN:
   `<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>`.
4. **Tabla ordenable Top 10 entidades** con columnas:
   entidad | pares | equivalentes | % equivalencia.
5. **Tabla distribución por Nivel Jerárquico**.
6. **Sección "Observaciones y errores"**:
   - Errores de la FASE 3 (si los hubo).
   - Alertas de campos críticos vacíos.
   - Top 10 pares con mayor conflicto (NO_EQUIVALENTE con score más alto).
7. **Footer** con fecha/hora ISO de la corrida + versión del modelo SBERT
   (está en el JSON).

Si hubo error crítico y NO se pudo ejecutar el CLI, el HTML debe ser un
reporte de INCIDENTE estilizado con EARM Design, explicando en qué fase
falló y por qué.

## FASE 6 – Envío del correo

Usa `mcp__...__gmail_create_draft` y luego envíalo (o usa la tool de
envío directo). Parámetros:

- **Para**: `dmorales@cnsc.gov.co`
- **CC**: `morales.1010020668@gmail.com`
- **Asunto**: `Reporte Semanal Listas de Elegibles – <FECHA_ISO>`
- **Cuerpo** (texto plano, 4-6 líneas):

  ```
  Buenas tardes,

  Se ejecutó la rutina semanal de Listas de Elegibles el <FECHA_ISO>.
  Se procesaron <N> registros: <X> equivalentes (<%>) y <Y> no
  equivalentes (<%>). Se adjuntan el Excel de resultados, el PDF de
  reporte y el HTML interactivo con el detalle.

  Cordialmente,
  Rutina automática – Despacho EARM – CNSC
  ```

- **Adjuntos OBLIGATORIOS** (los 3, si existen):
  1. `./output/resultados_<FECHA>.xlsx`
  2. `./output/reporte_<FECHA>.pdf`
  3. `./output/reporte_<FECHA>.html`

Si alguno no se generó, envía el correo con los que sí estén y menciona
EXPLÍCITAMENTE en el cuerpo cuál falta y por qué.

## REGLAS GENERALES

- **Nunca abortes en silencio**. Cada error se documenta y se envía.
- **No modifiques el archivo original de Drive**. Trabaja sobre copias.
- **Fechas siempre ISO `AAAA-MM-DD`**, zona horaria America/Bogota.
- Al finalizar, **imprime en la sesión un resumen** de las 6 fases con
  `✅` o `❌` por cada una, más el tiempo total de ejecución.

## Salida esperada al terminar

- Correo enviado a `dmorales@cnsc.gov.co` con CC a
  `morales.1010020668@gmail.com` con los 3 adjuntos (o los que se
  lograron generar).
- Los 3 archivos en `./output/`.
- Log en la sesión con el check ✅/❌ de cada fase.
- Tiempo total en segundos.
```

---

## Cómo actualizar esta rutina después

Si el Despacho necesita cambiar algo (nuevo destinatario de correo,
umbrales distintos, etc.), edita este archivo y ejecuta:

```python
from mcp_scheduled_tasks import update_scheduled_task
# lee el prompt nuevo de rutina_semanal.md y actualiza la task
```

O simplemente re-crea la task con el nuevo prompt usando
`mcp__scheduled-tasks__create_scheduled_task` con el mismo `taskId`.

## Cómo ver el historial de corridas

Los scheduled tasks de Claude Code se guardan en:
`C:\Users\dmorales\.claude\scheduled-tasks\<task-id>\`

Ahí está el `SKILL.md` con el prompt actual y las sesiones de cada
corrida pasada (logs completos).
