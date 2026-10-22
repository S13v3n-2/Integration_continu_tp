import csv

from src.projet.generation_csv import (
    generer_fichier_csv_idempotent,
    generer_tous_les_csv,
)

ENTETES_ATTENDUS = [
    "datetime_transaction",
    "iban_org",
    "pays_src",
    "banque_src",
    "iban_dest",
    "pays_dest",
    "montant",
]


def lire_csv(chemin):
    with open(chemin, newline="", encoding="utf-8") as fichier:
        return list(csv.reader(fichier))


def test_entetes_du_fichier(tmp_path):
    chemin = generer_fichier_csv_idempotent(batch_id=1, dossier_cible=str(tmp_path))
    assert lire_csv(chemin)[0] == ENTETES_ATTENDUS


def test_nombre_de_transactions_entre_5_et_10(tmp_path):
    chemin = generer_fichier_csv_idempotent(batch_id=1, dossier_cible=str(tmp_path))
    nb_transactions = len(lire_csv(chemin)) - 1  # sans l'entête
    assert 5 <= nb_transactions <= 10


def test_generation_deterministe(tmp_path):
    dossier_a = tmp_path / "a"
    dossier_b = tmp_path / "b"
    dossier_a.mkdir()
    dossier_b.mkdir()

    fichier_a = generer_fichier_csv_idempotent(batch_id=7, dossier_cible=str(dossier_a))
    fichier_b = generer_fichier_csv_idempotent(batch_id=7, dossier_cible=str(dossier_b))

    assert fichier_a.read_bytes() == fichier_b.read_bytes()


def test_batchs_differents_donnent_des_fichiers_differents(tmp_path):
    fichier_1 = generer_fichier_csv_idempotent(batch_id=1, dossier_cible=str(tmp_path))
    fichier_2 = generer_fichier_csv_idempotent(batch_id=2, dossier_cible=str(tmp_path))
    assert fichier_1.read_bytes() != fichier_2.read_bytes()


def test_pays_coherent_avec_la_banque_et_l_iban(tmp_path):
    chemin = generer_fichier_csv_idempotent(batch_id=3, dossier_cible=str(tmp_path))
    for ligne in lire_csv(chemin)[1:]:
        _, iban_org, pays_src, _, iban_dest, pays_dest, _ = ligne
        assert iban_org.startswith(pays_src)
        assert iban_dest.startswith(pays_dest)


def test_montants_positifs(tmp_path):
    chemin = generer_fichier_csv_idempotent(batch_id=3, dossier_cible=str(tmp_path))
    assert all(float(ligne[-1]) > 0 for ligne in lire_csv(chemin)[1:])


def test_generer_tous_les_csv(tmp_path):
    dossier = tmp_path / "raw"  # le dossier n'existe pas encore
    fichiers = generer_tous_les_csv(nb_batches=3, dossier_cible=str(dossier))

    assert [f.name for f in fichiers] == [
        "transactions_batch_0000.csv",
        "transactions_batch_0001.csv",
        "transactions_batch_0002.csv",
    ]
    assert all(f.exists() for f in fichiers)
