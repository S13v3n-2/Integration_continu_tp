FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src

# le worker regarde regulierement s'il y a de nouveaux fichiers dans le S3
CMD ["python", "-m", "src.projet.pipeline", "--mode", "worker", "--intervalle", "60"]
