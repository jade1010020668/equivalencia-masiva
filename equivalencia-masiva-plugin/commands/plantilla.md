---
description: Descarga la plantilla Excel con las 15 columnas requeridas y filas de ejemplo
argument-hint: [ruta/de/salida.xlsx] (opcional, default cwd)
allowed-tools: ["Bash", "mcp__equivalencia-masiva-core__generar_plantilla"]
---

# /plantilla — Generar plantilla Excel del pipeline EARM

Crea un archivo `.xlsx` con:

- Las 15 columnas obligatorias que el pipeline requiere
- Tooltips en cada encabezado explicando qué contenido va
- 3 filas de ejemplo (1 empleo base 4.0 + 2 listas candidatas)
- Pestaña "Instrucciones" con detalle completo

## Instrucciones para Claude

1. Si el usuario dio una ruta en `$ARGUMENTS`, úsala. Si no, usa el directorio
   actual (`./plantilla_equivalencia_masiva.xlsx`).

2. Llama a `mcp__equivalencia-masiva-core__generar_plantilla(ruta_salida=<path>)`.

3. Confirma al usuario:
   - Ruta exacta donde quedó el archivo
   - Tamaño (~10 KB)
   - Próximo paso: "Abre el archivo, reemplaza las filas de ejemplo con tus datos,
     y luego ejecuta `/analizar <tu-archivo>`."

4. Si el usuario está en Windows, ofrece abrirlo con `Bash(start <path>)`.
   Si en macOS: `Bash(open <path>)`. En Linux: `Bash(xdg-open <path>)`.

## Columnas requeridas (para referencia rápida)

1. `No. OPEC` — ID único
2. `Código` — código del manual de funciones
3. `Denominación` — nombre del cargo
4. `Grado` — entero
5. `Nivel Jerárquico` — Directivo/Asesor/Profesional/Técnico/Asistencial
6. `Orden` — Nacional/Territorial
7. `Naturaleza Jurídica` — Ministerio/Municipio/etc.
8. `Salario` — número en pesos
9. `Requisitos Estudio`
10. `Requisitos Experiencia`
11. `Funciones`
12. `Competencias Laborales`
13. `Competencias Comportamentales`
14. `modalidad` — "4.0" (base vigente) o "LISTAS"
15. `nombre_entidad`
