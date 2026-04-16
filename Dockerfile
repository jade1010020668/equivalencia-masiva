# Dockerfile para Equivalencia Masiva (Despacho EARM - CNSC)
#
# Build:
#   docker build -t equivalencia-masiva .
#
# Run:
#   docker run --rm -p 8501:8501 equivalencia-masiva
#
# La primera corrida descarga el modelo SBERT (~450 MB) y queda cacheado
# dentro del contenedor. Para persistir el cache entre corridas:
#   docker run --rm -p 8501:8501 -v ${PWD}/.hfcache:/root/.cache/huggingface equivalencia-masiva
#
# Python 3.11 se elige porque tiene wheels pre-compiladas de torch/sentence-transformers
# en todas las arquitecturas (Linux x64, ARM64), al contrario de 3.14 que aún no.

FROM python:3.11-slim

# Dependencias del sistema para compilar wheels si alguna no está pre-compilada
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar sólo requirements primero para aprovechar cache de Docker
COPY requirements.txt .

# Instalar torch CPU desde el índice oficial (evita torch GPU que pesa >2GB)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Copiar el código de la app
COPY . .

# Pre-descargar el modelo SBERT durante el build para que la primera corrida
# en producción no tenga que esperar la descarga.
# NOTA: esto hace la imagen ~500 MB más grande, pero elimina cold-start del usuario.
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('hiiamsid/sentence_similarity_spanish_es')" || \
    echo "Pre-download failed, will download at first use"

EXPOSE 8501

# Healthcheck para orquestadores (Kubernetes, Cloud Run, HF Spaces)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Ejecutar Streamlit en modo headless
CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
