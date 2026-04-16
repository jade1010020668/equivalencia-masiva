---
title: Equivalencia Masiva CNSC
emoji: ⚖️
colorFrom: blue
colorTo: indigo
sdk: streamlit
sdk_version: 1.56.0
app_file: app.py
pinned: false
license: apache-2.0
short_description: Análisis masivo de equivalencia de empleos para listas de elegibles CNSC
---

# ⚖️ Equivalencia Masiva de Empleos

**Despacho III — Comisionado Edwin Arturo Ruiz Moreno · CNSC**

Aplicación Streamlit para el análisis masivo de equivalencia de empleos a partir de listas de elegibles. Unifica en un solo flujo lo que antes requería dos herramientas separadas:

1. **Agrupamiento por entidad/nivel/grado** (antes `copy-of-criterio-base` en React).
2. **Análisis semántico SBERT** (antes `mismo_grado_.ipynb` en Google Colab).

---

## ¿Qué hace?

- Subes **un solo Excel** con todos los empleos base 4.0 y sus listas de elegibles candidatas.
- La app agrupa cada empleo base 4.0 con las listas que tienen el mismo grado, entidad y nivel jerárquico.
- Para cada par `(base, lista)` calcula cobertura semántica con SBERT sobre **5 aspectos**:
  Funciones · Requisitos Estudio · Requisitos Experiencia · Competencias Laborales · Competencias Comportamentales.
- Aplica la **misma lógica de decisión** del notebook `mismo_grado_.ipynb` (compuerta AND sobre umbrales).
- Descarga: **Excel consolidado** + **PDF detallado** + **Plantilla vacía** para empezar.

## ¿Cómo produce los mismos resultados que el notebook?

El módulo `core/semantic.py` es un **port fiel** del pipeline semántico del notebook:

| Aspecto | Notebook `mismo_grado_.ipynb` | `core/semantic.py` | Igual |
|---|---|---|---|
| Preprocesamiento | `procesar_bloque` + `normalizar_texto_func` + `split_by_bullet_lines` + `es_ruido` | Mismo código, port literal | ✅ |
| Modelo SBERT default | `hiiamsid/sentence_similarity_spanish_es` (STS_ES) | Mismo (configurable) | ✅ |
| Métrica de cobertura | `cobertura_prom_max_1 = mean(max(matriz, axis=1))` | Mismo | ✅ |
| Experiencia con jerarquía | `HIERARQUIA_EXPERIENCIA` + `verificar_jerarquia_experiencia` | Mismo | ✅ |
| Umbrales default | Funciones 0.60, Estudio 0.70, Comp. 0.65 | Mismo | ✅ |
| Pesos para score | Func 0.80, Est 0.20, CL 0.00, CC 0.00 | Mismo | ✅ |
| Compuerta AND | `nivel & salario & pasa_f & (pasa_e & pasa_l & pasa_c)` | Mismo | ✅ |

Si algún par produce un resultado distinto al notebook, es un **bug** — por favor reportarlo con el Excel de entrada.

---

## Instalación local

```bash
# 1. Clonar o copiar el proyecto
cd "C:\Users\dmorales\Downloads\listas de elejibles"

# 2. Instalar torch CPU (liviano, ~200 MB)
pip install torch --index-url https://download.pytorch.org/whl/cpu

# 3. Instalar el resto de dependencias
pip install -r requirements.txt

# 4. Arrancar la app
python -m streamlit run app.py
# O en Windows: doble click en run.bat
```

La app abrirá automáticamente tu navegador en `http://localhost:8501`.

**Primera corrida**: la app descarga el modelo SBERT `hiiamsid/sentence_similarity_spanish_es` (~450 MB) a `~/.cache/huggingface/`. Sólo pasa una vez.

## Estructura del proyecto

```
listas de elejibles/
├── app.py                      # Entry point Streamlit (UI completa)
├── config.py                   # Umbrales, pesos, modelo (todos del notebook)
├── requirements.txt            # Dependencias pinneadas
├── Dockerfile                  # Imagen para deployment
├── run.bat / run.sh            # Launchers locales
├── README.md                   # Este archivo
├── INSTRUCTIVO.md              # Guía paso a paso para usuarios finales
├── DEPLOYMENT.md               # Cómo publicar en URL pública
│
├── core/
│   ├── grouping.py             # Agrupador (entidad, nivel, grado)
│   ├── semantic.py             # Motor SBERT (port fiel del notebook)
│   ├── decision.py             # Compuerta AND del notebook
│   ├── report.py               # Generador de Excel consolidado
│   ├── pdf_report.py           # Generador de PDF detallado
│   └── template.py             # Generador de plantilla descargable
│
├── tests/
│   ├── test_grouping.py        # 5 tests del agrupador
│   └── test_decision.py        # 12 tests de la lógica de decisión
│
└── .streamlit/
    └── config.toml             # Tema visual
```

## Deployment público

Ver [DEPLOYMENT.md](DEPLOYMENT.md) para instrucciones de:

- **Hugging Face Spaces** (recomendado, gratis, privado opcional)
- **Streamlit Community Cloud**
- **Docker en servidor propio**

## Tests

```bash
python -m pytest tests/ -v
```

Espera `17 passed`. Los tests cubren:
- Agrupamiento con casos edge (bases huérfanas, múltiples bases en el mismo grupo, entidades distintas).
- Lógica de decisión: todas las combinaciones de AND-gate y scores ponderados.

## Créditos

- **Fuente 1**: `copy-of-criterio-base.zip` — App React/Vite del Despacho EARM que agrupa por entidad/nivel/grado.
- **Fuente 2**: `mismo_grado_.ipynb` — Notebook Python/Colab del Despacho EARM con análisis semántico SBERT.
- **Integración masiva**: este proyecto.

---

Despacho III · Comisionado Edwin Arturo Ruiz Moreno · Comisión Nacional del Servicio Civil
