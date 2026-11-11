"""Tests d'intégration : demandent Postgres et le S3 local (docker compose up -d db s3)."""
import shutil
import uuid

import psycopg
import pytest

from src.projet.config import config_db
from src.projet.generation_csv import generer_tous_les_csv
from src.projet.generation_images import generer_image_transactions
from src.projet.stockage_s3 import assurer_bucket, creer_client, envoyer_fichier, lister_cles
from src.projet.traitement_donnees import (
    calculer_flag_transaction_5000,
    calculer_somme_par_banque_src,
    calculer_somme_par_iban_dest,
    calculer_somme_par_iban_origine,
    read_transactions,
)
from src.projet.writing_postgres import connecter, traiter_nouveaux_fichiers
from tests.test_ocr import transactions_attendues

pytestmark = pytest.mark.integration

NB_FICHIERS = 3


@pytest.fixture
def base_temporaire(monkeypatch):
    """Base Postgres jetable, pour ne pas toucher aux données existantes."""
    nom = f"test_{uuid.uuid4().hex[:8]}"
    admin = {**config_db()}
    with psycopg.connect(**admin, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{nom}"')
    monkeypatch.setenv("POSTGRES_DB", nom)
    yield nom
    with psycopg.connect(**admin, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{nom}" WITH (FORCE)')


@pytest.fixture
def bucket():
    nom = f"test-{uuid.uuid4().hex[:8]}"
    client = creer_client()
    assurer_bucket(client, nom)
    yield client, nom
    for cle in lister_cles(client, nom):
        client.delete_object(Bucket=nom, Key=cle)
    client.delete_bucket(Bucket=nom)


@pytest.fixture
def csv_dans_s3(bucket, tmp_path):
    client, nom = bucket
    for fichier in generer_tous_les_csv(nb_batches=NB_FICHIERS, dossier_cible=str(tmp_path)):
        envoyer_fichier(client, nom, fichier)
    df = read_transactions(str(tmp_path / "transactions_batch_*.csv"))
    return client, nom, df


def lire_table(requete):
    with connecter() as conn:
        return conn.execute(requete).fetchall()


def test_les_valeurs_en_base_sont_les_bonnes(base_temporaire, csv_dans_s3):
    client, nom, df = csv_dans_s3

    traites, ignores = traiter_nouveaux_fichiers(client, nom)
    assert (traites, ignores) == (NB_FICHIERS, 0)

    for table, cle, attendu in [
        ("totaux_iban_org", "iban_org", calculer_somme_par_iban_origine(df)),
        ("totaux_banque_src", "banque_src", calculer_somme_par_banque_src(df)),
        ("totaux_iban_dest", "iban_dest", calculer_somme_par_iban_dest(df)),
    ]:
        en_base = {k: float(v) for k, v in lire_table(f"SELECT {cle}, montant_total FROM {table}")}
        assert en_base == pytest.approx(dict(zip(attendu[cle], attendu["montant_total"])))

    flags = calculer_flag_transaction_5000(df)
    montants = sorted(float(m[0]) for m in lire_table("SELECT montant FROM transactions_5000"))
    assert montants == pytest.approx(sorted(flags["montant"]))
    assert all(m > 5000 for m in montants)

    assert len(lire_table("SELECT 1 FROM fichiers_traites")) == NB_FICHIERS


def test_un_second_passage_ne_retraite_rien(base_temporaire, csv_dans_s3):
    client, nom, _ = csv_dans_s3
    traiter_nouveaux_fichiers(client, nom)
    avant = lire_table("SELECT iban_org, montant_total FROM totaux_iban_org ORDER BY 1")

    traites, ignores = traiter_nouveaux_fichiers(client, nom)

    assert (traites, ignores) == (0, NB_FICHIERS)
    assert lire_table("SELECT iban_org, montant_total FROM totaux_iban_org ORDER BY 1") == avant


def test_retry_apres_echec_d_insertion_sans_double_comptage(
    base_temporaire, csv_dans_s3, monkeypatch
):
    monkeypatch.setattr("src.projet.retry.time.sleep", lambda _: None)
    client, nom, df = csv_dans_s3
    restants = {"n": 2}

    def bug_insertion():
        if restants["n"] > 0:
            restants["n"] -= 1
            raise psycopg.OperationalError("echec simulé")

    traites, _ = traiter_nouveaux_fichiers(client, nom, avant_commit=bug_insertion)

    assert traites == NB_FICHIERS
    assert restants["n"] == 0
    total = float(lire_table("SELECT sum(montant_total) FROM totaux_iban_org")[0][0])
    assert total == pytest.approx(round(df["montant"].sum(), 2))
    assert len(lire_table("SELECT 1 FROM fichiers_traites")) == NB_FICHIERS


def test_echec_definitif_ne_laisse_rien_en_base(base_temporaire, csv_dans_s3, monkeypatch):
    monkeypatch.setattr("src.projet.retry.time.sleep", lambda _: None)
    client, nom, _ = csv_dans_s3

    def bug_permanent():
        raise psycopg.OperationalError("base indisponible")

    with pytest.raises(psycopg.OperationalError):
        traiter_nouveaux_fichiers(client, nom, avant_commit=bug_permanent)

    assert lire_table("SELECT 1 FROM fichiers_traites") == []
    assert lire_table("SELECT 1 FROM totaux_iban_org") == []


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract absent, a lancer dans le conteneur")
def test_image_lue_par_ocr_puis_inseree(base_temporaire, bucket, tmp_path):
    client, nom = bucket
    envoyer_fichier(client, nom, generer_image_transactions(batch_id=0, dossier_cible=str(tmp_path)))
    attendu = transactions_attendues(batch_id=0)

    assert traiter_nouveaux_fichiers(client, nom) == (1, 0)

    totaux = calculer_somme_par_iban_origine(attendu)
    en_base = {k: float(v) for k, v in lire_table("SELECT iban_org, montant_total FROM totaux_iban_org")}
    assert en_base == pytest.approx(dict(zip(totaux["iban_org"], totaux["montant_total"])))
    assert traiter_nouveaux_fichiers(client, nom) == (0, 1)


def test_image_illisible_ne_bloque_pas_les_autres_fichiers(base_temporaire, csv_dans_s3):
    client, nom, _ = csv_dans_s3
    client.put_object(Bucket=nom, Key="transactions_image_9999.png", Body=b"pas une image")

    traites, _ = traiter_nouveaux_fichiers(client, nom)

    assert traites == NB_FICHIERS
    noms = {ligne[0] for ligne in lire_table("SELECT nom_fichier FROM fichiers_traites")}
    assert "transactions_image_9999.png" not in noms
