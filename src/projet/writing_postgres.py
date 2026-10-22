import psycopg
import os
from pathlib import Path
from dotenv import load_dotenv

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


# Schéma des tables : nom -> instruction CREATE TABLE
SCHEMA = {
    "totaux_iban_org": """
        CREATE TABLE totaux_iban_org (
            id SERIAL PRIMARY KEY,
            iban_org VARCHAR(100),
            montant_total NUMERIC(18, 2)
        )
    """,
    "totaux_banque_src": """
        CREATE TABLE totaux_banque_src (
            id SERIAL PRIMARY KEY,
            banque_src VARCHAR(100),
            montant_total NUMERIC(18, 2)
        )
    """,
    "totaux_iban_dest": """
        CREATE TABLE totaux_iban_dest (
            id SERIAL PRIMARY KEY,
            iban_dest VARCHAR(100),
            montant_total NUMERIC(18, 2)
        )
    """,
    "transactions_5000": """
        CREATE TABLE transactions_5000 (
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


def creer_tables(cursor):
    """Supprime puis recrée toutes les tables du schéma."""
    for table, create_sql in SCHEMA.items():
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
        cursor.execute(create_sql)


def ecrire_dataframe(cursor, df, table: str):
    """Insère toutes les lignes du DataFrame dans la table (déjà créée).
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


if __name__ == "__main__":
    # 1. Traitement des données
    df_raw = read_transactions(str(BASE_DIR / "data/raw/transactions_batch_*.csv"))
    df_totaux_iban_org = calculer_somme_par_iban_origine(df_raw)
    df_totaux_bank_org = calculer_somme_par_banque_src(df_raw)
    df_totaux_iban_dest = calculer_somme_par_iban_dest(df_raw)
    df_transactions_5000 = calculer_flag_transaction_5000(df_raw)

    # 2. Connexion automatique et sécurisée grâce au bloc "with" (commit à la sortie)
    with psycopg.connect(
        host="localhost",
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    ) as conn:
        with conn.cursor() as cursor:
            creer_tables(cursor)
            ecrire_dataframe(cursor, df_totaux_iban_org, "totaux_iban_org")
            ecrire_dataframe(cursor, df_totaux_bank_org, "totaux_banque_src")
            ecrire_dataframe(cursor, df_totaux_iban_dest, "totaux_iban_dest")
            ecrire_dataframe(cursor, df_transactions_5000, "transactions_5000")

    print("Résultats écrits dans PostgreSQL.")
