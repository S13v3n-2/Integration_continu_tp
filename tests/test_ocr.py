import pandas as pd
import pytest

from src.projet.ocr import COLONNES, corriger_iban, lire_transactions_image, parser_transactions

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


def test_texte_vide_donne_un_dataframe_vide_avec_les_bonnes_colonnes():
    df = parser_transactions("")
    assert df.empty
    assert list(df.columns) == COLONNES
    assert isinstance(df, pd.DataFrame)


def test_image_sans_transaction_leve_une_erreur(monkeypatch):
    monkeypatch.setattr("src.projet.ocr.extraire_texte", lambda contenu: "rien d'utile")
    with pytest.raises(ValueError):
        lire_transactions_image(b"peu importe")
