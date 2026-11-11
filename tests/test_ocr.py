import shutil

import pandas as pd
import pytest

from src.projet.generation_csv import generer_donnees_transactions
from src.projet.generation_images import DECALAGE_BATCH, generer_image_transactions
from src.projet.ocr import COLONNES, corriger_iban, lire_transactions_image, parser_transactions


def transactions_attendues(batch_id: int) -> pd.DataFrame:
    """Ce que l'image contient, tel que les donnees ont ete generees."""
    lignes = generer_donnees_transactions(DECALAGE_BATCH + batch_id, nb_lignes=8)
    df = pd.DataFrame(lignes, columns=COLONNES)
    df["montant"] = df["montant"].astype(float)
    return df


LIGNE = "2026-01-01 00:01:00 FR7612345678901234567890000 FR BNP Paribas DE89370400440532013000001 DE 1234.50"


def test_parse_une_ligne_complete():
    df = parser_transactions(LIGNE)
    assert list(df.columns) == COLONNES
    assert df.iloc[0].to_dict() == {
        "datetime_transaction": "2026-01-01 00:01:00",
        "iban_org": "FR7612345678901234567890000",
        "pays_src": "FR",
        "banque_src": "BNP Paribas",
        "iban_dest": "DE89370400440532013000001",
        "pays_dest": "DE",
        "montant": 1234.50,
    }


def test_banque_avec_plusieurs_mots():
    ligne = "2026-01-01 00:01:00 IT7612345 IT Intesa Sanpaolo ES8912345 ES 10.00"
    assert parser_transactions(ligne).iloc[0]["banque_src"] == "Intesa Sanpaolo"


def test_ignore_les_lignes_parasites():
    texte = f"bruit\n\n{LIGNE}\n12 xx ??\n{LIGNE}"
    assert len(parser_transactions(texte)) == 2


def test_virgule_decimale_acceptee():
    ligne = LIGNE.replace("1234.50", "1234,50")
    assert parser_transactions(ligne).iloc[0]["montant"] == 1234.50


def test_corrige_les_confusions_de_l_ocr_dans_l_iban():
    assert corriger_iban("FR76O234I678l") == "FR7602341678" + "1"


def test_iban_coupe_par_l_ocr_est_recolle():
    ligne = "2026-01-01 16:40:07 CH7612345678901 234567890007 CH UBS IT8937040044053201 3000007 IT 242.70"
    df = parser_transactions(ligne)
    assert df.iloc[0]["iban_org"] == "CH7612345678901234567890007"
    assert df.iloc[0]["iban_dest"] == "IT89370400440532013000007"
    assert df.iloc[0]["banque_src"] == "UBS"


def test_texte_vide_donne_un_dataframe_vide_avec_les_bonnes_colonnes():
    df = parser_transactions("")
    assert df.empty
    assert list(df.columns) == COLONNES
    assert isinstance(df, pd.DataFrame)


def test_image_sans_transaction_leve_une_erreur(monkeypatch):
    monkeypatch.setattr("src.projet.ocr.extraire_texte", lambda contenu: "rien d'utile")
    with pytest.raises(ValueError):
        lire_transactions_image(b"peu importe")


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract absent, a lancer dans le conteneur")
def test_ocr_relit_une_image_generee(tmp_path):
    chemin = generer_image_transactions(batch_id=0, dossier_cible=str(tmp_path))

    df = lire_transactions_image(chemin.read_bytes())

    assert df.equals(transactions_attendues(batch_id=0))
