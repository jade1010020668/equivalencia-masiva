#!/usr/bin/env python
"""
Hook PostToolUse — valida Excels de OPEC automáticamente al guardarlos.

Se dispara después de cualquier Write tool. Revisa si el archivo escrito es un
Excel (.xlsx/.xls) con nombre que sugiere OPEC/equivalencia, y corre validación
rápida de las 15 columnas requeridas por el pipeline EARM.

- Si todo OK → retorna silenciosamente (exit 0, sin output).
- Si faltan columnas → imprime mensaje de alerta al stderr del hook
  (el usuario lo ve en Claude Code como notificación del hook).

No modifica el archivo, no bloquea el Write — solo alerta.

Variables de entorno esperadas (Claude Code las inyecta):
- CLAUDE_TOOL_INPUT: JSON con el input de la tool (file_path, content, etc.)
- CLAUDE_PLUGIN_ROOT: path del plugin (se usa para llegar al proyecto padre)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


# Palabras clave en el nombre del archivo que indican contexto EARM/OPEC
KEYWORDS = ("opec", "equivalencia", "elegibles", "empleo")

# Columnas requeridas (duplicadas aquí para no depender de pandas en el hook)
REQUIRED_COLUMNS = [
    "No. OPEC", "Código", "Denominación", "Grado", "Nivel Jerárquico",
    "Orden", "Naturaleza Jurídica", "Salario", "Requisitos Estudio",
    "Requisitos Experiencia", "Funciones", "Competencias Laborales",
    "Competencias Comportamentales", "modalidad", "nombre_entidad",
]


def main() -> int:
    """Devuelve 0 en éxito, >0 en error del propio hook (no del Excel)."""
    raw = os.environ.get("CLAUDE_TOOL_INPUT")
    if not raw:
        return 0  # Nada que hacer

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return 0

    file_path = payload.get("file_path") or payload.get("filePath")
    if not file_path:
        return 0

    path = Path(str(file_path))
    name_lower = path.name.lower()

    # Sólo actúa si parece un Excel de OPEC/equivalencia
    if not (path.suffix.lower() in (".xlsx", ".xls")
            and any(kw in name_lower for kw in KEYWORDS)):
        return 0

    if not path.exists():
        return 0  # El archivo puede todavía no estar en disco

    # Validación ligera — leemos solo el header
    try:
        from openpyxl import load_workbook
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        headers = [str(c.value).strip() if c.value is not None else ""
                   for c in next(ws.iter_rows(min_row=1, max_row=1))]
        wb.close()
    except Exception as exc:
        print(f"[equivalencia-masiva] ⚠ No pude leer {path.name}: {exc}", file=sys.stderr)
        return 0

    faltantes = [c for c in REQUIRED_COLUMNS if c not in headers]

    if not faltantes:
        # Todo OK — mensaje positivo corto en stderr del hook
        print(
            f"[equivalencia-masiva] ✓ {path.name} tiene las 15 columnas del pipeline EARM. "
            f"Puedes analizarlo con /analizar.",
            file=sys.stderr,
        )
        return 0

    # Faltan columnas — alertar
    print(
        f"[equivalencia-masiva] ⚠ {path.name} no es un Excel válido del pipeline EARM.\n"
        f"    Faltan {len(faltantes)} columna(s): {', '.join(repr(c) for c in faltantes[:5])}"
        + (f" (+{len(faltantes)-5} más)" if len(faltantes) > 5 else "") + "\n"
        f"    Usa /plantilla para descargar el formato correcto.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
