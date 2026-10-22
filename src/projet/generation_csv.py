import csv
import random
from datetime import datetime, timezone
from pathlib import Path


def generer_donnees_transactions(batch_id: int, nb_lignes: int = 10):
    """Génère des transactions déterministes avec pays et montants pseudo-aléatoires."""
    
    # Instance dédiée pour garantir la reproductibilité selon le batch_id, on fixe le random
    rng = random.Random(batch_id)
    
    # Listes de référence pour les tirages pseudo-aléatoires
    PAYS_DISPONIBLES = ["FR", "DE", "ES", "IT", "BE", "NL", "CH", "GB"]
    BANQUES_PAR_PAYS = {
        "FR": "BNP Paribas",
        "DE": "Deutsche Bank",
        "ES": "Banco Santander",
        "IT": "Intesa Sanpaolo",
        "BE": "KBC Bank",
        "NL": "ING Bank",
        "CH": "UBS",
        "GB": "Barclays"
    }
    # Initialisation de la liste de données
    donnees = []
    timestamp_base = 1767225600 + (batch_id * 60)
    
    for i in range(nb_lignes):
        dt_ligne = datetime.fromtimestamp(timestamp_base + i, tz=timezone.utc)
        horodatage = dt_ligne.strftime("%Y-%m-%d %H:%M:%S")
        
        # Tirage pseudo-aléatoire du pays source et destination
        pays_src = rng.choice(PAYS_DISPONIBLES)
        pays_dest = rng.choice(PAYS_DISPONIBLES)
        
        banque_src = BANQUES_PAR_PAYS[pays_src]
        montant = round(rng.uniform(10.0, 10000.0), 2)
        
        # Création de la transaction
        transaction = [
            horodatage,
            f"{pays_src}7612345678901234567890{i:03d}",  # IBAN cohérent avec le pays
            pays_src,
            banque_src,
            f"{pays_dest}89370400440532013000{i:03d}",
            pays_dest,
            f"{montant:.2f}"
        ]
        donnees.append(transaction)
        
    return donnees


def generer_fichier_csv_idempotent(batch_id: int, dossier_cible: str = ".") -> Path:
    """Crée un fichier CSV de façon idempotente."""
    # Initialisation de l'entete du csv
    entetes = [
        "datetime_transaction",
        "iban_org",
        "pays_src",
        "banque_src",
        "iban_dest",
        "pays_dest",
        "montant"
    ]
    
    nom_fichier = f"transactions_batch_{batch_id:04d}.csv"
    chemin_fichier = Path(dossier_cible) / nom_fichier

    lignes = generer_donnees_transactions(batch_id=batch_id, nb_lignes=10)

    with open(chemin_fichier, mode="w", newline="", encoding="utf-8") as fichier:
        # Creation du fichier 
        writer = csv.writer(fichier)
        # Creation de l'entetes du csv
        writer.writerow(entetes)
        # Creation des lignes du CSV
        writer.writerows(lignes)

    return chemin_fichier

def generer_tous_les_csv(nb_batches: int = 60, dossier_cible: str = "./data/raw") -> list[Path]:
    """Génère les fichiers CSV des batchs 0 à nb_batches - 1."""
    Path(dossier_cible).mkdir(parents=True, exist_ok=True)
    return [
        generer_fichier_csv_idempotent(batch_id=i, dossier_cible=dossier_cible)
        for i in range(nb_batches)
    ]


if __name__ == "__main__":
    # Test d'idempotence : un même batch produira toujours le même fichier
    for fichier in generer_tous_les_csv():
        print(f"Fichier généré : {fichier}")
