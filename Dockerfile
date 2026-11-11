FROM python:3.12-slim AS base

# tesseract sert a lire les transactions contenues dans les images
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src


# image utilisee pour lancer les tests dans un conteneur
FROM base AS test

COPY requirements-dev.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY tests ./tests

CMD ["pytest"]


# image finale : le worker regarde regulierement s'il y a de nouveaux fichiers dans le S3
FROM base AS worker

CMD ["python", "-m", "src.projet.pipeline", "--mode", "worker", "--intervalle", "60"]
