import hashlib
import psycopg
import os
from pathlib import Path
from dotenv import load_dotenv

try:
    from .traitement_donnees import (
        read_transactions,
        calculer_somme_par_iban_origine,
        calculer_somme_par_banque_src,
        calculer_somme_par_iban_dest,
        calculer_flag_transaction_5000,
    )
except ImportError:
    # Lancement direct du fichier (bouton "Run" de l'IDE)
    from traitement_donnees import (
        read_transactions,
        calculer_somme_par_iban_origine,
        calculer_somme_par_banque_src,
        calculer_somme_par_iban_dest,
        calculer_flag_transaction_5000,
    )

# 1. Définir le chemin vers le fichier .env
# __file__ = chemin de ce script (writing_postgres.py)
# parents[2] = racine du projet
BASE_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BASE_DIR / ".env"

# 2. Charger explicitement le .env
load_dotenv(dotenv_path=ENV_PATH)


# Schéma des tables : les tables sont persistantes (CREATE TABLE IF NOT EXISTS).
# Les tables de totaux ont une clé primaire métier pour permettre l'upsert cumulatif.
SCHEMA = {
    "fichiers_traites": """
        CREATE TABLE IF NOT EXISTS fichiers_traites (
            nom_fichier VARCHAR(255) PRIMARY KEY,
            hash_sha256 CHAR(64) NOT NULL UNIQUE,
            traite_le TIMESTAMP NOT NULL DEFAULT now()
        )
    """,
    "totaux_iban_org": """
        CREATE TABLE IF NOT EXISTS totaux_iban_org (
            iban_org VARCHAR(100) PRIMARY KEY,
            montant_total NUMERIC(18, 2) NOT NULL
        )
    """,
    "totaux_banque_src": """
        CREATE TABLE IF NOT EXISTS totaux_banque_src (
            banque_src VARCHAR(100) PRIMARY KEY,
            montant_total NUMERIC(18, 2) NOT NULL
        )
    """,
    "totaux_iban_dest": """
        CREATE TABLE IF NOT EXISTS totaux_iban_dest (
            iban_dest VARCHAR(100) PRIMARY KEY,
            montant_total NUMERIC(18, 2) NOT NULL
        )
    """,
    "transactions_5000": """
        CREATE TABLE IF NOT EXISTS transactions_5000 (
            id SERIAL PRIMARY KEY,
            datetime_transaction TIMESTAMP,
            iban_org VARCHAR(100),
            pays_src VARCHAR(10),
            banque_src VARCHAR(100),
            iban_dest VARCHAR(100),
            pays_dest VARCHAR(10),
            montant NUMERIC(18, 2)
        )
    """,
}


def connecter() -> psycopg.Connection:
    """Ouvre une connexion à PostgreSQL à partir des variables du .env."""
    return psycopg.connect(
        host="localhost",
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def creer_tables(cursor):
    """Crée les tables du schéma si elles n'existent pas déjà."""
    for create_sql in SCHEMA.values():
        cursor.execute(create_sql)


def calculer_hash(chemin: Path) -> str:
    """Empreinte SHA-256 du contenu d'un fichier."""
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def est_deja_traite(cursor, nom_fichier: str, hash_fichier: str) -> bool:
    """Vrai si le fichier (par son nom ou son contenu) a déjà été traité."""
    cursor.execute(
        "SELECT 1 FROM fichiers_traites WHERE nom_fichier = %s OR hash_sha256 = %s",
        (nom_fichier, hash_fichier),
    )
    return cursor.fetchone() is not None


def upsert_totaux(cursor, df, table: str, cle: str):
    """Ajoute les montants du DataFrame aux totaux déjà présents (upsert cumulatif)."""
    if df.empty:
        return
    lignes = list(
        df[[cle, "montant_total"]].astype(object).itertuples(index=False, name=None)
    )
    cursor.executemany(
        f"""
        INSERT INTO {table} ({cle}, montant_total) VALUES (%s, %s::numeric)
        ON CONFLICT ({cle}) DO UPDATE
        SET montant_total = {table}.montant_total + EXCLUDED.montant_total
        """,
        lignes,
    )


def ecrire_dataframe(cursor, df, table: str):
    """Insère toutes les lignes du DataFrame dans la table.
    Args:
        cursor: curseur psycopg ouvert.
        df: DataFrame dont les colonnes correspondent à celles de la table.
        table: nom de la table cible.
    """
    if df.empty:
        return

    colonnes = ", ".join(df.columns)
    placeholders = ", ".join(["%s"] * len(df.columns))
    # astype(object) convertit les types numpy en types Python natifs
    lignes = list(df.astype(object).itertuples(index=False, name=None))
    cursor.executemany(
        f"INSERT INTO {table} ({colonnes}) VALUES ({placeholders})", lignes
    )


def traiter_fichier(conn, chemin: Path, hash_fichier: str):
    """Traite un fichier CSV et écrit ses résultats en base.
    Les écritures et l'enregistrement dans fichiers_traites sont dans la même
    transaction : en cas d'erreur tout est annulé et un retry retraite le fichier.
    """
    df_raw = read_transactions(str(chemin))

    with conn.transaction():
        with conn.cursor() as cursor:
            upsert_totaux(cursor, calculer_somme_par_iban_origine(df_raw), "totaux_iban_org", "iban_org")
            upsert_totaux(cursor, calculer_somme_par_banque_src(df_raw), "totaux_banque_src", "banque_src")
            upsert_totaux(cursor, calculer_somme_par_iban_dest(df_raw), "totaux_iban_dest", "iban_dest")
            ecrire_dataframe(cursor, calculer_flag_transaction_5000(df_raw), "transactions_5000")
            cursor.execute(
                "INSERT INTO fichiers_traites (nom_fichier, hash_sha256) VALUES (%s, %s)",
                (chemin.name, hash_fichier),
            )


def traiter_nouveaux_fichiers(dossier: Path) -> tuple[int, int]:
    """Traite les CSV du dossier qui n'ont pas encore été traités.
    Returns:
        (nombre de fichiers traités, nombre de fichiers ignorés)
    """
    traites, ignores = 0, 0
    with connecter() as conn:
        with conn.transaction():
            with conn.cursor() as cursor:
                creer_tables(cursor)

        for chemin in sorted(Path(dossier).glob("transactions_batch_*.csv")):
            hash_fichier = calculer_hash(chemin)
            with conn.cursor() as cursor:
                deja_traite = est_deja_traite(cursor, chemin.name, hash_fichier)
            if deja_traite:
                ignores += 1
                continue
            traiter_fichier(conn, chemin, hash_fichier)
            traites += 1
    return traites, ignores


if __name__ == "__main__":
    traites, ignores = traiter_nouveaux_fichiers(BASE_DIR / "data" / "raw")
    print(f"{traites} fichier(s) traité(s), {ignores} déjà traité(s) ignoré(s).")
