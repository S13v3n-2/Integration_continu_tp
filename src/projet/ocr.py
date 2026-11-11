import io
import re

import pandas as pd

COLONNES = [
    "datetime_transaction",
    "iban_org",
    "pays_src",
    "banque_src",
    "iban_dest",
    "pays_dest",
    "montant",
]

# date heure, iban, pays, banque (mots libres), iban, pays, montant
MOTIF_LIGNE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+"
    r"([A-Z]{2}[0-9OIl]+)\s+([A-Z]{2})\s+(.+?)\s+"
    r"([A-Z]{2}[0-9OIl]+)\s+([A-Z]{2})\s+"
    r"(\d+[.,]\d{2})$"
)

# confusions classiques de l'ocr dans la partie numerique d'un iban
CONFUSIONS = str.maketrans({"O": "0", "I": "1", "l": "1"})


def corriger_iban(iban: str) -> str:
    """Garde le code pays et remet des chiffres dans le reste de l'iban."""
    return iban[:2] + iban[2:].translate(CONFUSIONS)


def extraire_texte(contenu: bytes) -> str:
    """Lit le texte d'une image avec tesseract (installe dans l'image docker)."""
    import pytesseract
    from PIL import Image

    return pytesseract.image_to_string(Image.open(io.BytesIO(contenu)), config="--psm 6")


def parser_transactions(texte: str) -> pd.DataFrame:
    """Transforme le texte reconnu en DataFrame de transactions (fonction pure).

    Les lignes qui ne ressemblent pas a une transaction sont ignorees.
    """
    lignes = []
    for brut in texte.splitlines():
        trouve = MOTIF_LIGNE.match(brut.strip())
        if trouve is None:
            continue
        horodatage, iban_org, pays_src, banque, iban_dest, pays_dest, montant = trouve.groups()
        lignes.append(
            [
                horodatage,
                corriger_iban(iban_org),
                pays_src,
                banque,
                corriger_iban(iban_dest),
                pays_dest,
                float(montant.replace(",", ".")),
            ]
        )
    return pd.DataFrame(lignes, columns=COLONNES)


def lire_transactions_image(contenu: bytes) -> pd.DataFrame:
    """Extrait les transactions d'une image. Leve ValueError si rien n'est reconnu."""
    df = parser_transactions(extraire_texte(contenu))
    if df.empty:
        raise ValueError("aucune transaction reconnue dans l'image")
    return df
