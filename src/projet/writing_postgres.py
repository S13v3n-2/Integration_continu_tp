import hashlib
import logging
from collections.abc import Callable

import psycopg

from .config import config_db
from .retry import avec_retry
from .stockage_s3 import lister_cles, telecharger_contenu
from .traitement_donnees import (
    calculer_flag_transaction_5000,
    calculer_somme_par_banque_src,
    calculer_somme_par_iban_dest,
    calculer_somme_par_iban_origine,
    lire_transactions_fichier,
)

logger = logging.getLogger(__name__)

EXTENSIONS_TRAITEES = (".csv", ".png")

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
    """Ouvre une connexion à PostgreSQL."""
    return psycopg.connect(**config_db())


def creer_tables(cursor):
    """Crée les tables du schéma si elles n'existent pas déjà."""
    for create_sql in SCHEMA.values():
        cursor.execute(create_sql)


def calculer_hash(contenu: bytes) -> str:
    """Empreinte SHA-256 du contenu d'un fichier."""
    return hashlib.sha256(contenu).hexdigest()


def marquer_traite(cursor, nom_fichier: str, hash_fichier: str) -> bool:
    """Enregistre le fichier comme traité. Renvoie False s'il l'était déjà (nom ou contenu)."""
    cursor.execute(
        """
        INSERT INTO fichiers_traites (nom_fichier, hash_sha256) VALUES (%s, %s)
        ON CONFLICT DO NOTHING
        """,
        (nom_fichier, hash_fichier),
    )
    return cursor.rowcount == 1


def lister_fichiers_traites(conn) -> set[str]:
    with conn.cursor() as cursor:
        cursor.execute("SELECT nom_fichier FROM fichiers_traites")
        return {ligne[0] for ligne in cursor.fetchall()}


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


@avec_retry(tentatives=4, delai=0.5, exceptions=(psycopg.OperationalError,))
def inserer_resultats(
    nom_fichier: str,
    contenu: bytes,
    avant_commit: Callable[[], None] | None = None,
) -> bool:
    """Traite le contenu d'un CSV et écrit les résultats en base. Renvoie False si ignoré.

    Tout se passe dans une seule transaction, y compris l'enregistrement dans
    fichiers_traites : si ça plante, rien n'est écrit et le retry repart de zéro,
    donc un fichier n'est jamais compté deux fois.
    avant_commit sert à simuler un bug d'insertion dans les tests.
    """
    df_raw = lire_transactions_fichier(nom_fichier, contenu)
    hash_fichier = calculer_hash(contenu)

    with connecter() as conn, conn.transaction(), conn.cursor() as cursor:
        if not marquer_traite(cursor, nom_fichier, hash_fichier):
            return False
        upsert_totaux(cursor, calculer_somme_par_iban_origine(df_raw), "totaux_iban_org", "iban_org")
        upsert_totaux(cursor, calculer_somme_par_banque_src(df_raw), "totaux_banque_src", "banque_src")
        upsert_totaux(cursor, calculer_somme_par_iban_dest(df_raw), "totaux_iban_dest", "iban_dest")
        ecrire_dataframe(cursor, calculer_flag_transaction_5000(df_raw), "transactions_5000")
        if avant_commit is not None:
            avant_commit()
    return True


def initialiser_base():
    with connecter() as conn, conn.transaction(), conn.cursor() as cursor:
        creer_tables(cursor)


def traiter_nouveaux_fichiers(
    client,
    bucket: str,
    avant_commit: Callable[[], None] | None = None,
) -> tuple[int, int]:
    """Traite les CSV du bucket qui n'ont pas encore été traités.

    Returns:
        (nombre de fichiers traités, nombre de fichiers ignorés)
    """
    initialiser_base()
    with connecter() as conn:
        deja_traites = lister_fichiers_traites(conn)

    traites, ignores = 0, 0
    for cle in lister_cles(client, bucket):
        if not cle.lower().endswith(EXTENSIONS_TRAITEES):
            continue
        if cle in deja_traites:
            ignores += 1
            continue
        contenu = telecharger_contenu(client, bucket, cle)
        try:
            if inserer_resultats(cle, contenu, avant_commit):
                traites += 1
            else:
                ignores += 1
        except (ValueError, OSError):
            # image illisible ou tesseract absent : on passe au fichier suivant,
            # le fichier n'est pas marque comme traite donc il sera retente
            logger.exception("fichier %s non traite", cle)
    return traites, ignores
