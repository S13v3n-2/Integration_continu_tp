from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from .config import config_s3
from .retry import avec_retry

ERREURS_S3 = (BotoCoreError, ClientError)


def creer_client():
    """Client boto3 branché sur le S3 local."""
    cfg = config_s3()
    return boto3.client(
        "s3",
        endpoint_url=cfg["endpoint"],
        aws_access_key_id=cfg["access_key"],
        aws_secret_access_key=cfg["secret_key"],
        region_name=cfg["region"],
        config=Config(
            retries={"max_attempts": 1},  # les retries sont gérés par avec_retry
            connect_timeout=5,
            read_timeout=15,
            s3={"addressing_style": "path"},
        ),
    )


@avec_retry(tentatives=5, delai=1.0, exceptions=ERREURS_S3)
def assurer_bucket(client, bucket: str):
    """Crée le bucket s'il n'existe pas encore."""
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError as erreur:
        if erreur.response["Error"]["Code"] not in ("404", "NoSuchBucket", "NotFound"):
            raise
        client.create_bucket(Bucket=bucket)


def envoyer_fichier(client, bucket: str, chemin: Path) -> str:
    """Envoie un fichier local dans le bucket, la clé est son nom. Renvoie la clé."""
    client.upload_file(str(chemin), bucket, chemin.name)
    return chemin.name


def lister_cles(client, bucket: str, prefixe: str = "") -> list[str]:
    """Liste les clés du bucket (toutes les pages), triées par nom."""
    cles = []
    for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefixe):
        cles.extend(obj["Key"] for obj in page.get("Contents", []))
    return sorted(cles)


@avec_retry(tentatives=4, delai=0.5, exceptions=ERREURS_S3)
def telecharger_contenu(client, bucket: str, cle: str) -> bytes:
    """Récupère le contenu d'un objet, avec retry si la récupération échoue."""
    return client.get_object(Bucket=bucket, Key=cle)["Body"].read()
