# Rutina semanal — Listas de Elegibles (Despacho EARM, CNSC)

Prompt exacto programado en la rutina automática de Claude Code.

- **Schedule**: cada miércoles, 03:00 hora Bogotá (GMT-5).
- **Task ID**: `LISTA E EARM`.

---

## Prompt de la rutina

```
# RUTINA SEMANAL – PROCESAMIENTO AUTOMÁTICO DE LISTAS DE ELEGIBLES
# Despacho EARM – CNSC
Eres el agente automático del Despacho III EARM. Esta rutina corre todos los miércoles.
Ejecutas TODO sin intervención humana. NUNCA abortes en silencio; el correo SIEMPRE debe salir.

## ANTES DE EMPEZAR
Instala dependencias y crea carpetas:
    pip install -r requirements.txt -q
    pip install "mcp[cli]>=1.0" -q
    mkdir -p input output

## FASE 1 – OBTENER INSUMO DE GOOGLE DRIVE
1. Busca en Drive: mcp__Google-Drive__search_files con query `title contains 'API LISTAS ELEGIBLES'`
2. Si hay varias versiones, toma la de modifiedTime más reciente.
3. Descárgala con mcp__Google-Drive__download_file_content → guarda el blob base64 en:
       ./input/API_LISTAS_ELEGIBLES.xlsx
   Código para decodificar y guardar:
       import json, base64
       data = json.load(open('<ruta_tool_result>'))
       raw = base64.b64decode(data['content'][0]['embeddedResource']['contents']['blob'])
       open('./input/API_LISTAS_ELEGIBLES.xlsx','wb').write(raw)
4. Verifica hojas con: pd.ExcelFile('./input/API_LISTAS_ELEGIBLES.xlsx').sheet_names
   Debe incluir "VACANTES DEFINITIVAS" Y "LISTAS DE ELEGIBLES".
   Si falta alguna, documenta el error y salta a FASE 5 (HTML de incidente) → FASE 6.

## FASE 2 – CONSOLIDAR EL EXCEL
Ejecuta este bloque Python exacto:

    import pandas as pd
    COLS = [
        'modalidad','nombre_entidad','No. OPEC','Código','Denominación','Grado',
        'Nivel Jerárquico','Orden','Naturaleza Jurídica','Salario',
        'Requisitos Estudio','Requisitos Experiencia','Funciones',
        'Competencias Laborales','Competencias Comportamentales'
    ]
    df_vac = pd.read_excel('./input/API_LISTAS_ELEGIBLES.xlsx',
                           sheet_name='VACANTES DEFINITIVAS')[COLS]
    df_lis = pd.read_excel('./input/API_LISTAS_ELEGIBLES.xlsx',
                           sheet_name='LISTAS DE ELEGIBLES')[COLS]
    df_cons = pd.concat([df_vac, df_lis], ignore_index=True)
    with pd.ExcelWriter('./input/base_consolidada.xlsx', engine='openpyxl') as w:
        df_cons.to_excel(w, sheet_name='CONSOLIDACION', index=False)
    print(f'Consolidado: {len(df_cons)} filas — modalidad: {df_cons["modalidad"].unique()}')

NO normalizar la columna "modalidad". El pipeline acepta 4 numérico Y "LISTAS " texto.

## FASE 3 – EJECUTAR EL PIPELINE
Obtén la fecha ISO Bogotá:
    from datetime import datetime; from zoneinfo import ZoneInfo
    FECHA = datetime.now(ZoneInfo("America/Bogota")).strftime("%Y-%m-%d")

Ejecuta y captura stdout (JSON) + stderr (logs):
    python run_pipeline.py \
        --input ./input/base_consolidada.xlsx \
        --output-dir ./output \
        --date <FECHA>

Códigos de salida:
  0 → éxito (puede incluir cero pares si todas las bases son huérfanas). SIEMPRE continúa a FASE 4.
  1 → archivo no encontrado o ilegible → salta a FASE 5 (incidente) → FASE 6.
  2 → faltan columnas → salta a FASE 5 (incidente) → FASE 6.
  3 → error de dependencias → salta a FASE 5 (incidente) → FASE 6.
  4 → error durante análisis → salta a FASE 5 (incidente) → FASE 6.

Con exit 0, el script SIEMPRE produce: ./output/resumen_<FECHA>.json
Con exit 0 Y pares > 0, también produce: resultados_<FECHA>.xlsx y reporte_<FECHA>.pdf

## FASE 4 – ANÁLISIS
Lee ./output/resumen_<FECHA>.json y extrae:
    import json
    R = json.loads(open(f'./output/resumen_{FECHA}.json').read())
    total_registros = (len de df_cons calculado en FASE 2)
    total_grupos    = R['total_grupos']
    huerfanos       = R['bases_huerfanas']
    total_pares     = R['total_pares_analizados']
    equiv           = R['totales']['EQUIVALENTE']
    no_equiv        = R['totales']['NO_EQUIVALENTE']
    pct_eq          = R['totales']['pct_equivalentes']
    tiene_pares     = total_pares > 0

## FASE 5 – REPORTE HTML (DISEÑO EARM)
Ejecuta el siguiente bloque Python para generar ./output/reporte_<FECHA>.html.
Adapta las variables con los valores reales de FASE 4.

    FECHA_STR = FECHA   # "2026-04-17"
    # --- filas de la tabla top entidades ---
    top_rows = ""
    for e in R['top_entidades']:
        pct = round(e['equivalentes']/e['pares']*100,1) if e['pares'] else 0
        top_rows += f"<tr><td>{e['entidad']}</td><td class='mono'>{e['pares']}</td><td class='mono'>{e['equivalentes']}</td><td class='mono'>{pct}%</td></tr>"
    if not top_rows:
        top_rows = "<tr><td colspan='4' style='text-align:center;color:#9E9E9E;padding:16px'>Sin pares analizados esta semana</td></tr>"
    # --- filas distribución nivel ---
    nivel_rows = ""
    for n in R['distribucion_nivel']:
        nivel_rows += f"<tr><td>{n['nivel']}</td><td class='mono'>{n['pares']}</td></tr>"
    if not nivel_rows:
        nivel_rows = "<tr><td colspan='2' style='text-align:center;color:#9E9E9E;padding:16px'>Sin distribución disponible</td></tr>"
    # --- alerta huérfanas ---
    alerta = ""
    if huerfanos > 0 and not tiene_pares:
        alerta = f"""<div class="alert-box"><span class="alert-icon">⚠️</span><div>
        <strong>{huerfanos} bases 4.0 sin lista candidata.</strong> Ninguna lista comparte
        (entidad, Nivel Jerárquico, Grado) con las vacantes. Sin análisis semántico esta semana.
        Revisar el insumo Drive antes de la próxima ejecución.</div></div>"""
    # --- pill de estado ---
    status = "SIN PARES" if not tiene_pares else "COMPLETADO"
    status_color = "#F59E0B" if not tiene_pares else "#10B981"

    html = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>REPORTE SEMANAL LISTAS DE ELEGIBLES — {FECHA_STR}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{--yellow:#FFEE58;--dark:#2C2C2C;--text:#424242;--body:#FAFAFA;--glass:rgba(255,255,255,0.82);--emerald:#10B981;--red:#EF4444;--amber:#F59E0B}}
body{{font-family:'Plus Jakarta Sans',sans-serif;background:var(--body);color:var(--text);min-height:100vh;position:relative;overflow-x:hidden}}
body::before{{content:'';position:fixed;top:-120px;left:-120px;width:500px;height:500px;background:rgba(255,238,88,0.22);border-radius:50%;filter:blur(120px);pointer-events:none;z-index:0}}
body::after{{content:'';position:fixed;bottom:-120px;right:-120px;width:500px;height:500px;background:rgba(16,185,129,0.15);border-radius:50%;filter:blur(120px);pointer-events:none;z-index:0}}
.wrap{{position:relative;z-index:1;max-width:980px;margin:0 auto;padding:32px 24px 64px}}
header{{background:var(--glass);backdrop-filter:blur(24px);border-radius:16px;padding:28px 32px;display:flex;align-items:center;gap:20px;margin-bottom:28px;border:1px solid rgba(255,238,88,0.35)}}
.logo{{width:56px;height:56px;background:var(--yellow);border-radius:14px;display:flex;align-items:center;justify-content:center;font-size:28px;flex-shrink:0}}
.header-text h1{{font-size:1.22rem;font-weight:800;color:var(--dark);text-transform:uppercase;letter-spacing:.04em;line-height:1.2}}
.header-text .sub{{font-size:.84rem;color:#757575;margin-top:4px;font-family:'JetBrains Mono',monospace}}
.pill{{display:inline-flex;align-items:center;gap:6px;padding:6px 14px;border-radius:99px;font-size:.78rem;font-weight:600;white-space:nowrap;margin-left:auto;background:rgba(16,185,129,0.12);color:{status_color};border:1px solid rgba(16,185,129,0.3)}}
.dot{{width:8px;height:8px;border-radius:50%;background:{status_color};animation:pulse 1.5s infinite}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.4}}}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:16px;margin-bottom:28px}}
.card{{background:var(--glass);backdrop-filter:blur(24px);border-radius:14px;padding:20px 22px;border:1px solid rgba(255,255,255,.7);box-shadow:0 2px 12px rgba(0,0,0,.06)}}
.card-label{{font-size:.75rem;color:#757575;font-weight:600;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px}}
.card-value{{font-size:1.9rem;font-weight:800;color:var(--dark);line-height:1}}
.card-value.green{{color:#16A34A}}.card-value.red{{color:var(--red)}}.card-value.amber{{color:var(--amber)}}
.card-sub{{font-size:.75rem;color:#9E9E9E;margin-top:5px}}
.glass-panel{{background:var(--glass);backdrop-filter:blur(24px);border-radius:14px;padding:20px 24px;border:1px solid rgba(255,255,255,.7);box-shadow:0 2px 12px rgba(0,0,0,.06)}}
section{{margin-bottom:28px}}
section h2{{font-size:1rem;font-weight:700;color:var(--dark);margin-bottom:14px;padding-left:10px;border-left:3px solid var(--yellow)}}
table{{width:100%;border-collapse:collapse;font-size:.85rem}}
thead th{{text-align:left;padding:10px 12px;font-size:.73rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#757575;border-bottom:2px solid rgba(0,0,0,.07)}}
tbody tr{{border-bottom:1px solid rgba(0,0,0,.05);transition:background .15s}}
tbody tr:hover{{background:rgba(255,238,88,.08)}}
tbody td{{padding:9px 12px}}
.mono{{font-family:'JetBrains Mono',monospace;font-size:.82rem}}
.chart-wrap{{max-width:320px;margin:0 auto;padding:8px 0}}
.alert-box{{background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.3);border-radius:12px;padding:16px 20px;display:flex;gap:14px;align-items:flex-start;margin-bottom:28px;font-size:.88rem;line-height:1.6}}
.alert-icon{{font-size:1.6rem;flex-shrink:0}}
.obs li{{font-size:.88rem;padding-left:20px;position:relative;line-height:1.6;list-style:none;margin-bottom:6px}}
.obs li::before{{content:'→';position:absolute;left:0;color:#FDD835;font-weight:700}}
footer{{text-align:center;padding-top:32px;font-size:.72rem;letter-spacing:.15em;color:#9E9E9E;text-transform:uppercase}}
</style></head>
<body><div class="wrap">
<header>
  <div class="logo">⚖️</div>
  <div class="header-text">
    <h1>Reporte semanal listas de elegibles</h1>
    <div class="sub">Despacho EARM · CNSC · {FECHA_STR}</div>
  </div>
  <div class="pill"><span class="dot"></span>{status}</div>
</header>
{alerta}
<div class="cards">
  <div class="card"><div class="card-label">Registros procesados</div><div class="card-value">{total_registros}</div><div class="card-sub">{len(df_vac)} vacantes + {len(df_lis)} listas</div></div>
  <div class="card"><div class="card-label">Equivalentes</div><div class="card-value green">{equiv}</div><div class="card-sub">{pct_eq}% del total</div></div>
  <div class="card"><div class="card-label">No equivalentes</div><div class="card-value red">{no_equiv}</div><div class="card-sub">{round(100-pct_eq,1)}% del total</div></div>
  <div class="card"><div class="card-label">% Equivalencia</div><div class="card-value amber">{pct_eq}%</div><div class="card-sub">{total_pares} pares analizados</div></div>
</div>
<section><h2>Distribución de veredictos</h2><div class="glass-panel"><div class="chart-wrap"><canvas id="doughnut" width="300" height="300"></canvas></div></div></section>
<section><h2>Top entidades por pares analizados</h2><div class="glass-panel"><table><thead><tr><th>Entidad</th><th>Pares</th><th>Equivalentes</th><th>% Eq.</th></tr></thead><tbody>{top_rows}</tbody></table></div></section>
<section><h2>Distribución por nivel jerárquico</h2><div class="glass-panel"><table><thead><tr><th>Nivel</th><th>Pares</th></tr></thead><tbody>{nivel_rows}</tbody></table></div></section>
<section><h2>Observaciones y alertas</h2><div class="glass-panel"><ul class="obs">
  <li>Bases huérfanas (sin lista candidata del mismo nivel/grado): <strong>{huerfanos}</strong> de {total_grupos}.</li>
</ul></div></section>
<footer>Equivalencia Masiva v1.0 — Edwin Arturo Ruiz Moreno — Comisionado CNSC 2026</footer>
</div>
<script>
const eq={equiv},noEq={no_equiv};
const hasData=(eq+noEq)>0;
new Chart(document.getElementById('doughnut'),{{type:'doughnut',data:{{
  labels:hasData?['Equivalentes','No Equivalentes']:['Sin pares analizados'],
  datasets:[{{data:hasData?[eq,noEq]:[1],backgroundColor:hasData?['#16A34A','#EF4444']:['#E5E7EB'],borderWidth:0,hoverOffset:6}}]
}},options:{{cutout:'70%',plugins:{{legend:{{position:'bottom'}},tooltip:{{callbacks:{{label:ctx=>' '+ctx.label+': '+ctx.parsed+(hasData?' ('+Math.round(ctx.parsed/(eq+noEq)*100)+'%)':'')}}}}}}}}}}});
</script></body></html>"""

    with open(f'./output/reporte_{FECHA}.html','w',encoding='utf-8') as f:
        f.write(html)
    print(f'HTML generado: ./output/reporte_{FECHA}.html')

## FASE 6 – CORREO (borrador HTML — listo para enviar)
IMPORTANTE: el Gmail MCP solo crea borradores (no hay tool de envío directo).
El borrador queda en Gmail con el reporte completo en el cuerpo HTML.
El destinatario puede abrirlo y enviarlo manualmente, O el administrador
puede configurar un trigger de Gmail para auto-envío.

Lee el HTML generado en FASE 5 y úsalo como htmlBody:

    html_body = open(f'./output/reporte_{FECHA}.html', encoding='utf-8').read()

    # Cuerpo texto plano (fallback)
    if tiene_pares:
        body_plain = f"""Buenas tardes,

Se ejecutó la rutina semanal de Listas de Elegibles el {FECHA}.
Se procesaron {total_registros} registros: {equiv} equivalentes ({pct_eq}%)
y {no_equiv} no equivalentes ({round(100-pct_eq,1)}%).
El reporte interactivo completo se encuentra en el cuerpo HTML de este correo.

Archivos generados:
  ✅ resultados_{FECHA}.xlsx — Excel consolidado con veredictos
  ✅ reporte_{FECHA}.pdf    — PDF detallado institucional
  ✅ reporte_{FECHA}.html   — Reporte interactivo (en cuerpo HTML)

Cordialmente,
Rutina automática – Despacho EARM – CNSC"""
    else:
        body_plain = f"""Buenas tardes,

Se ejecutó la rutina semanal de Listas de Elegibles el {FECHA}.
Se procesaron {total_registros} registros: {equiv} equivalentes ({pct_eq}%)
y {no_equiv} no equivalentes. {huerfanos} bases son huérfanas (sin lista candidata).
El reporte con el diagnóstico completo se encuentra en el cuerpo HTML de este correo.

Archivos generados:
  ⚠️ resultados_{FECHA}.xlsx — No generado (sin pares para analizar)
  ⚠️ reporte_{FECHA}.pdf    — No generado (sin pares para analizar)
  ✅ reporte_{FECHA}.html   — Reporte de diagnóstico (en cuerpo HTML)

Cordialmente,
Rutina automática – Despacho EARM – CNSC"""

Llama a mcp__Gmail__create_draft con:
  - to: ["dmorales@cnsc.gov.co"]
  - cc: ["morales.1010020668@gmail.com"]
  - subject: f"Reporte Semanal Listas de Elegibles – {FECHA}"
  - body: body_plain  (texto plano)
  - htmlBody: html_body  (HTML completo del reporte)

Confirma el draftId en el resumen final.

## REGLAS
- Nunca abortes en silencio.
- No modifiques el archivo original de Drive.
- Fechas siempre ISO AAAA-MM-DD zona America/Bogota.
- Al final, imprime resumen de 6 fases con ✅/❌ y tiempo total.
```

---

## Correcciones aplicadas (historial)

| Fecha | Fix |
|-------|-----|
| 2026-04-17 | `_modalidad_clean`: int(4) → "4.0" para round-trip Excel |
| 2026-04-17 | `run_pipeline.py`: exit 0 con JSON de ceros cuando bases son huérfanas |
| 2026-04-17 | `mcp_server/server.py`: normalización OPEC y modalidad en `analizar_par` |
| 2026-04-17 | `core/semantic.py`: fallback TF-IDF offline cuando SBERT no disponible |
| 2026-04-17 | Rutina: FASE 5 genera HTML siempre (código Python integrado) |
| 2026-04-17 | Rutina: FASE 6 usa `htmlBody` con el reporte embebido en el correo |
