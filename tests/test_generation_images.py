from PIL import Image

from src.projet.generation_csv import generer_donnees_transactions
from src.projet.generation_images import (
    DECALAGE_BATCH,
    formater_ligne,
    generer_image_transactions,
    generer_toutes_les_images,
)


def test_formater_ligne_met_les_champs_dans_l_ordre():
    transaction = ["2026-01-01 00:00:00", "FR76A", "FR", "BNP Paribas", "DE89B", "DE", "123.45"]
    assert formater_ligne(transaction) == "2026-01-01 00:00:00 FR76A FR BNP Paribas DE89B DE 123.45"


def test_image_png_valide(tmp_path):
    chemin = generer_image_transactions(batch_id=1, dossier_cible=str(tmp_path))
    assert chemin.name == "transactions_image_0001.png"
    with Image.open(chemin) as image:
        assert image.format == "PNG"
        assert image.width > 500 and image.height > 100


def test_generation_deterministe(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    fichier_a = generer_image_transactions(batch_id=2, dossier_cible=str(a))
    fichier_b = generer_image_transactions(batch_id=2, dossier_cible=str(b))
    assert fichier_a.read_bytes() == fichier_b.read_bytes()


def test_les_images_ne_reprennent_pas_les_transactions_des_csv():
    csv_batch = generer_donnees_transactions(batch_id=0, nb_lignes=8)
    image_batch = generer_donnees_transactions(batch_id=DECALAGE_BATCH, nb_lignes=8)
    assert csv_batch != image_batch


def test_generer_toutes_les_images(tmp_path):
    fichiers = generer_toutes_les_images(nb_images=3, dossier_cible=str(tmp_path / "raw"))
    assert [f.name for f in fichiers] == [
        "transactions_image_0000.png",
        "transactions_image_0001.png",
        "transactions_image_0002.png",
    ]
