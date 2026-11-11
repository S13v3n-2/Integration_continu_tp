from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .generation_csv import generer_donnees_transactions

# on decale les batchs pour ne pas reproduire les transactions des CSV
DECALAGE_BATCH = 1000
TAILLE_POLICE = 30
MARGE = 30


def formater_ligne(transaction: list[str]) -> str:
    """Met une transaction sur une ligne, champs separes par des espaces."""
    return " ".join(transaction)


def generer_image_transactions(batch_id: int, dossier_cible: str = ".", nb_lignes: int = 8) -> Path:
    """Dessine les transactions d'un batch dans une image PNG (deterministe)."""
    transactions = generer_donnees_transactions(DECALAGE_BATCH + batch_id, nb_lignes=nb_lignes)
    lignes = [formater_ligne(t) for t in transactions]

    police = ImageFont.load_default(size=TAILLE_POLICE)
    hauteur_ligne = TAILLE_POLICE + 14
    largeur = int(max(police.getlength(ligne) for ligne in lignes)) + 2 * MARGE
    hauteur = hauteur_ligne * len(lignes) + 2 * MARGE

    image = Image.new("RGB", (largeur, hauteur), "white")
    dessin = ImageDraw.Draw(image)
    for i, ligne in enumerate(lignes):
        dessin.text((MARGE, MARGE + i * hauteur_ligne), ligne, fill="black", font=police)

    chemin = Path(dossier_cible) / f"transactions_image_{batch_id:04d}.png"
    image.save(chemin)
    return chemin


def generer_toutes_les_images(nb_images: int = 5, dossier_cible: str = "./data/raw") -> list[Path]:
    Path(dossier_cible).mkdir(parents=True, exist_ok=True)
    return [generer_image_transactions(i, dossier_cible) for i in range(nb_images)]
