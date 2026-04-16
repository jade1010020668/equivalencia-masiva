# 🚀 Guía de Deployment — Equivalencia Masiva

Esta guía explica cómo publicar la aplicación en una URL pública para que otros miembros del Despacho y colegas del CNSC puedan usarla sin instalar nada localmente.

---

## ⚠️ Consideraciones de privacidad antes de publicar

Antes de elegir opción de deployment, considera:

| Preocupación | Por qué importa | Mitigación |
|---|---|---|
| **Datos sensibles en tránsito** | Los usuarios suben Excel que pueden contener información de OPEC aún no publicada | Usa HTTPS (todas las opciones de abajo lo traen por defecto) |
| **Acceso abierto al mundo** | Cualquiera puede subir archivos y consumir tus recursos | Preferir plataformas con auth opcional (HF Spaces, Streamlit Cloud) |
| **Retención de datos** | ¿La plataforma guarda los Excel que los usuarios suben? | Streamlit Cloud y HF Spaces NO persisten archivos subidos entre sesiones por default |
| **Compliance** | Datos del CNSC pueden tener regulaciones de habeas data | Para datos genuinamente sensibles, usa deployment interno (Docker en servidor del CNSC) |

**Recomendación general del Despacho**: empezar con **Hugging Face Spaces en modo privado** (solo miembros autorizados) y ampliar a público sólo si los datos procesados son OPEC ya publicadas.

---

## Opción 1: Hugging Face Spaces (RECOMENDADA) ⭐

**Ventajas**:
- Gratis para uso normal (~16 GB RAM, 2 vCPU).
- Optimizado para apps ML (SBERT + Streamlit = combinación nativa).
- Soporta visibilidad **pública** o **privada** (solo tú y colaboradores invitados).
- Modelo SBERT se descarga a caché compartido, no en cada corrida.
- URL pública estable: `https://huggingface.co/spaces/{usuario}/{nombre-app}`

**Pasos**:

### A. Crear cuenta en Hugging Face (1 vez)

1. Ir a https://huggingface.co/join
2. Crear cuenta con tu correo institucional del CNSC.
3. Confirmar email.

### B. Crear el Space

1. Ir a https://huggingface.co/new-space
2. **Owner**: tu usuario.
3. **Space name**: `equivalencia-masiva` (o el nombre que prefieras).
4. **License**: "apache-2.0" (o "other" si prefieres no licenciar).
5. **Space SDK**: **Streamlit**.
6. **Hardware**: "CPU basic · Free" (suficiente con el pre-caching de embeddings).
7. **Visibility**:
   - **Public** → cualquiera con el link puede usarla.
   - **Private** → solo tú + colaboradores invitados explícitamente.
8. Click en **"Create Space"**.

### C. Subir los archivos

**Opción B1 — Por la web (más fácil, sin Git)**:

1. En la página del Space, click en **"Files"** → **"Add file"** → **"Upload files"**.
2. Arrastra TODOS los archivos del proyecto:
   - `app.py`
   - `config.py`
   - `requirements.txt`
   - `README.md`
   - Carpetas `core/` y `.streamlit/` (con sus archivos)
3. **Commit message**: "Initial deploy"
4. Click en **"Commit changes to main"**.

**Opción B2 — Por Git (más profesional)**:

```bash
cd "C:\Users\dmorales\Downloads\listas de elejibles"
git init
git add .
git commit -m "Initial deploy"
git remote add origin https://huggingface.co/spaces/{tu-usuario}/equivalencia-masiva
git push -u origin main
```

HF te pedirá un token de autenticación (lo generas en https://huggingface.co/settings/tokens).

### D. Esperar a que el Space arranque

HF automáticamente:
1. Detecta que es una Streamlit app (por `app.py` + `requirements.txt`).
2. Instala las dependencias (tarda 3-5 minutos la primera vez).
3. Descarga el modelo SBERT (~450 MB) al cache del Space.
4. Arranca `streamlit run app.py`.

Puedes ver el progreso en la pestaña **"Logs"** del Space.

### E. Compartir la URL

Cuando el Space esté "Running", tu URL pública es:

```
https://huggingface.co/spaces/{tu-usuario}/equivalencia-masiva
```

Puedes compartirla con colegas del Despacho. Si configuraste el Space como **privado**, solo quienes inviertas explícitamente pueden entrar (desde **"Settings" → "Collaborators"**).

---

## Opción 2: Streamlit Community Cloud

**Ventajas**:
- Gratis y de uso ilimitado para apps personales.
- URL pública estable: `https://{usuario}-{app}-{hash}.streamlit.app`.
- Conectado a GitHub: cada `git push` redespliega.

**Desventajas**:
- Tier gratuito tiene **1 GB RAM** → ajustado para STS Spanish (~450 MB del modelo + ~400 MB de torch). **Recomendamos usar MiniLM** en esta opción para no tocar el límite.
- Requiere repo en GitHub.

**Pasos**:

### A. Subir el código a GitHub

```bash
cd "C:\Users\dmorales\Downloads\listas de elejibles"
git init
git add .
git commit -m "Initial commit"
# Crea un repo vacío en github.com/new y luego:
git remote add origin https://github.com/{usuario}/equivalencia-masiva.git
git push -u origin main
```

### B. Ir a Streamlit Cloud

1. https://share.streamlit.io/
2. Sign in con tu cuenta de GitHub.
3. Click **"New app"**.
4. **Repository**: selecciona `equivalencia-masiva`.
5. **Branch**: `main`.
6. **Main file path**: `app.py`.
7. **App URL**: elige un sufijo (ej: `equivalencia-despacho-earm`).
8. (Opcional) **Advanced settings** → Python version: `3.11`.

### C. Ajuste recomendado para el tier gratuito

Edita `config.py` antes del deploy:

```python
SBERT_MODEL_NAME = SBERT_MODEL_FAST  # MiniLM en vez de STS Spanish
```

MiniLM pesa ~120 MB y deja más RAM libre para pandas y Streamlit.

### D. Click en "Deploy"

El build tarda 5-10 minutos la primera vez. Luego cada `git push` a main redespliega automáticamente.

---

## Opción 3: Docker en servidor propio

Si tienes un servidor interno del CNSC o una VPS, puedes correr el contenedor Docker directamente:

```bash
# Clonar el proyecto
cd /opt
git clone <url-del-repo> equivalencia-masiva
cd equivalencia-masiva

# Build
docker build -t equivalencia-masiva .

# Run (persistiendo el cache del modelo)
docker run -d \
    --name equivalencia-masiva \
    --restart unless-stopped \
    -p 8501:8501 \
    -v $PWD/.hfcache:/root/.cache/huggingface \
    equivalencia-masiva
```

Luego ponle un reverse proxy con HTTPS (nginx + certbot) apuntando a `localhost:8501`.

### Con docker-compose

```yaml
version: "3.8"
services:
  equivalencia:
    build: .
    ports:
      - "8501:8501"
    volumes:
      - ./.hfcache:/root/.cache/huggingface
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8501/_stcore/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

---

## Opción 4: Railway / Render (pagadas)

Ambas soportan Streamlit directo con `streamlit run app.py` como comando de start. Necesitas credit card aunque los tiers iniciales son ~$5/mes.

### Railway

1. https://railway.app/new → **Deploy from GitHub repo**
2. Selecciona el repo.
3. Variables de entorno: ninguna necesaria.
4. Start command: `streamlit run app.py --server.port=$PORT --server.address=0.0.0.0`

### Render

1. https://render.com/ → **New → Web Service**
2. Conecta el repo.
3. **Environment**: Python 3.11
4. **Build command**: `pip install -r requirements.txt`
5. **Start command**: `streamlit run app.py --server.port=$PORT --server.address=0.0.0.0 --server.headless=true`

---

## Comparativa rápida

| Opción | Costo | RAM | Público/Privado | Tiempo setup | Recomendado para |
|---|---|---|---|---|---|
| **HF Spaces** ⭐ | Gratis | 16 GB | Ambos | 10 min | **El uso normal del Despacho** |
| Streamlit Cloud | Gratis | 1 GB | Público | 15 min | Repositorios ya en GitHub |
| Docker propio | Gratis + server | Depende | Privado | 30+ min | Datos muy sensibles, servidor interno |
| Railway/Render | ~$5/mes | Variable | Ambos | 15 min | Control total con CI/CD |

---

## Checklist antes de publicar

- [ ] Probé la app localmente con un Excel real y los resultados coinciden con el notebook.
- [ ] Subí la plantilla a la app y verifiqué que se descarga correctamente.
- [ ] Probé generar el PDF con el botón "Generar informe PDF detallado".
- [ ] Leí la sección de privacidad de este documento.
- [ ] Decidí si la app será pública o privada.
- [ ] Elegí plataforma (HF Spaces / Streamlit Cloud / Docker propio).
- [ ] Tengo cuenta en la plataforma elegida.

---

Para cualquier duda sobre deployment, revisa los logs de la plataforma elegida — usualmente los errores más comunes son: dependencias faltantes, RAM insuficiente (baja a MiniLM) o puerto incorrecto (usa `$PORT` en Railway/Render).
