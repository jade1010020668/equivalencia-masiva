# equivalencia-masiva — Claude Code plugin

> Plugin oficial del **Despacho III — Comisionado Edwin Arturo Ruiz Moreno (EARM)** de la Comisión Nacional del Servicio Civil (CNSC).
>
> Automatiza el análisis masivo de equivalencia de empleos entre empleos base vigentes (OPEC modalidad 4.0) y listas de elegibles candidatas (OPEC modalidad LISTAS).

## What this plugin does

Instead of opening the Streamlit app to upload an Excel and click through analyses, any member of the Despacho with Claude Code can now:

- Say *"analízame C:/data/opec_abril.xlsx"* → Claude runs `/analizar` automatically.
- Get conversational reports and follow-up questions in natural language.
- Delegate rigorous validation to the `equivalencia-validator` subagent.
- Generate templates, Excel reports, and PDF reports on demand.

Everything is a faithful port of `mismo_grado_.ipynb` (the original notebook the Despacho used manually) plus the grouping logic from `copy-of-criterio-base` (the React app for grouping by entity/level/grade).

## Components

| Component | Count | Purpose |
|---|---|---|
| Slash commands | 3 | `/analizar`, `/plantilla`, `/reporte` |
| Agents | 1 | `equivalencia-validator` (rigorous review) |
| Skills | 1 | `flujo-equivalencia-earm` (auto-loaded context) |
| Hooks | 1 | `PostToolUse` validates saved OPEC Excels |
| MCP server | 1 | 7 tools exposing `core/` as callable functions |

### Slash commands

- **`/plantilla [ruta]`** — Generates a blank Excel template with 15 required columns, tooltips, and 3 example rows.
- **`/analizar <path.xlsx>`** — Runs the full pipeline: grouping + SBERT semantic analysis + AND-gate decision.
- **`/reporte <path.xlsx> [--pdf|--excel|--ambos]`** — Generates consolidated Excel and/or detailed PDF reports.

### MCP tools

- `validar_columnas(ruta_excel)` — Quick header check
- `agrupar_excel(ruta_excel)` — Group by entity/level/grade
- `analizar_par(ruta_excel, opec_base, opec_lista)` — Single pair deep-dive
- `analizar_masivo(ruta_excel, ...thresholds)` — Full batch analysis
- `generar_plantilla(ruta_salida)` — Blank template
- `generar_reporte_excel(run_id)` — Consolidated Excel
- `generar_reporte_pdf(run_id)` — Detailed PDF

### Agent

**`equivalencia-validator`** — Invoked automatically when the user asks for rigorous review of results. Cites CNSC legal framework (Decreto 1083/2015, Ley 2418/2024), detects borderline cases (scores within 5% of threshold), and flags false negatives/positives.

### Skill

**`flujo-equivalencia-earm`** — Auto-loaded context document that teaches Claude the Despacho's terminology, thresholds (0.60/0.70/0.65), experience hierarchy, and reporting format. Fires whenever the user mentions OPEC, listas de elegibles, or equivalencia de empleos.

### Hook

**`PostToolUse` on Write** — Whenever Claude writes an `.xlsx` file whose name contains `opec`, `equivalencia`, `elegibles`, or `empleo`, the hook runs a lightweight validation of the 15 required columns. Silent on success; alerts on missing columns.

## Installation

### Prerequisites

- Claude Code installed with plugins support.
- Python 3.11+ with the project's dependencies: `pip install -r ../requirements.txt` + `pip install 'mcp[cli]'`.
- Cloned full project tree (the MCP server imports `core/`, which is one level up).

### Install

```bash
cd C:/Users/dmorales/Downloads/listas\ de\ elejibles/
claude plugins install ./equivalencia-masiva-plugin
```

### Verify

Inside Claude Code:

```
/plantilla
```

Should generate a `plantilla_equivalencia_masiva.xlsx` in the current directory. If it does, the MCP server is working.

For the full walkthrough in Spanish for Despacho members, see [`INSTALAR.md`](INSTALAR.md).

## Architecture

```
equivalencia-masiva-plugin/
├── .claude-plugin/plugin.json      — plugin manifest
├── .mcp.json                       — MCP server registration
├── commands/                       — 3 slash commands (analizar, plantilla, reporte)
├── agents/                         — equivalencia-validator subagent
├── skills/flujo-equivalencia-earm/ — terminology + thresholds + methodology
├── hooks/                          — automatic OPEC Excel validator
└── mcp_server/                     — FastMCP server exposing core/
    ├── server.py                   — 7 tools
    └── pyproject.toml              — dependencies
```

The MCP server imports from the parent project (`core/grouping.py`, `core/semantic.py`, etc.) via `PYTHONPATH` injection in `.mcp.json`. This keeps the plugin and the Streamlit app in sync — any fix to `core/` applies to both.

## Author

**Despacho III — Comisionado Edwin Arturo Ruiz Moreno**
Comisión Nacional del Servicio Civil (CNSC), Colombia

- License: Apache 2.0
- Version: 0.1.0
- Homepage: https://huggingface.co/despacho-earm/equivalencia-masiva
