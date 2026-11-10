import os
from pathlib import Path

from dotenv import load_dotenv

# racine du projet
BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=BASE_DIR / ".env")

DOSSIER_RAW = BASE_DIR / "data" / "raw"


def config_db() -> dict:
    """Paramètres de connexion à PostgreSQL, lus dans l'environnement."""
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "dbname": os.getenv("POSTGRES_DB"),
        "user": os.getenv("POSTGRES_USER"),
        "password": os.getenv("POSTGRES_PASSWORD"),
    }


def config_s3() -> dict:
    """Paramètres du service S3 local, lus dans l'environnement."""
    return {
        "endpoint": os.getenv("S3_ENDPOINT", "http://localhost:8333"),
        "access_key": os.getenv("S3_ACCESS_KEY", "local"),
        "secret_key": os.getenv("S3_SECRET_KEY", "local-secret"),
        "bucket": os.getenv("S3_BUCKET", "transactions"),
        "region": os.getenv("S3_REGION", "us-east-1"),
    }
