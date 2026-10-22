import pandas as pd

from src.projet.generation_csv import generer_tous_les_csv
from src.projet.traitement_donnees import (
    calculer_flag_transaction_5000,
    calculer_somme_par_banque_src,
    calculer_somme_par_iban_dest,
    calculer_somme_par_iban_origine,
    read_transactions,
)


def transactions_exemple() -> pd.DataFrame:
    """Petit jeu de données écrit à la main : les résultats attendus sont calculables de tête."""
    return pd.DataFrame(
        {
            "iban_org": ["A", "A", "B", "C"],
            "banque_src": ["BNP", "BNP", "UBS", "UBS"],
            "iban_dest": ["X", "Y", "X", "X"],
            "montant": [100.00, 5000.00, 5000.01, 200.50],
        }
    )


def test_somme_par_iban_origine():
    resultat = calculer_somme_par_iban_origine(transactions_exemple())
    assert dict(zip(resultat["iban_org"], resultat["montant_total"])) == {
        "A": 5100.00,
        "B": 5000.01,
        "C": 200.50,
    }


def test_somme_par_iban_origine_triee_par_montant_decroissant():
    resultat = calculer_somme_par_iban_origine(transactions_exemple())
    assert list(resultat["iban_org"]) == ["A", "B", "C"]


def test_somme_par_banque_src():
    resultat = calculer_somme_par_banque_src(transactions_exemple())
    assert dict(zip(resultat["banque_src"], resultat["montant_total"])) == {
        "BNP": 5100.00,
        "UBS": 5200.51,
    }


def test_somme_par_iban_dest():
    resultat = calculer_somme_par_iban_dest(transactions_exemple())
    assert dict(zip(resultat["iban_dest"], resultat["montant_total"])) == {
        "X": 5300.51,
        "Y": 5000.00,
    }


def test_flag_5000_exclut_le_seuil_exact():
    resultat = calculer_flag_transaction_5000(transactions_exemple())
    assert list(resultat["montant"]) == [5000.01]


def test_dataframes_vides():
    vide = pd.DataFrame(columns=["iban_org", "banque_src", "iban_dest", "montant"])
    assert calculer_somme_par_iban_origine(vide).empty
    assert calculer_somme_par_banque_src(vide).empty
    assert calculer_somme_par_iban_dest(vide).empty
    assert calculer_flag_transaction_5000(vide).empty


def test_traitement_de_fichiers_generes(tmp_path):
    """La génération et le traitement s'enchaînent : les totaux sont cohérents avec les données."""
    generer_tous_les_csv(nb_batches=3, dossier_cible=str(tmp_path))
    df = read_transactions(str(tmp_path / "transactions_batch_*.csv"))

    assert len(df) == 30  # 3 fichiers de 10 transactions

    total_attendu = round(df["montant"].sum(), 2)
    assert round(calculer_somme_par_iban_origine(df)["montant_total"].sum(), 2) == total_attendu
    assert round(calculer_somme_par_banque_src(df)["montant_total"].sum(), 2) == total_attendu
    assert round(calculer_somme_par_iban_dest(df)["montant_total"].sum(), 2) == total_attendu

    assert (calculer_flag_transaction_5000(df)["montant"] > 5000).all()
