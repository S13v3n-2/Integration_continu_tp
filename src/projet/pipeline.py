import subprocess
from pathlib import Path

try:
    # Lancement en module : python -m src.projet.pipeline
    from .generation_csv import generer_tous_les_csv
    from .writing_postgres import traiter_nouveaux_fichiers
except ImportError:
    # Lancement direct du fichier (bouton "Run" de l'IDE)
    from generation_csv import generer_tous_les_csv
    from writing_postgres import traiter_nouveaux_fichiers

# parents[2] = racine du projet
BASE_DIR = Path(__file__).resolve().parents[2]
DOSSIER_RAW = BASE_DIR / "data" / "raw"


def lancer_base_de_donnees():
    """Démarre le conteneur Postgres et attend que son healthcheck soit OK."""
    subprocess.run(
        ["docker", "compose", "up", "-d", "db", "--wait"],
        cwd=BASE_DIR,
        check=True,
    )


def main():
    # 1. Génération des fichiers CSV
    fichiers = generer_tous_les_csv(dossier_cible=str(DOSSIER_RAW))
    print(f"{len(fichiers)} fichiers CSV générés dans {DOSSIER_RAW}")

    # 2. Setup de la base de données relationnelle (persistante)
    lancer_base_de_donnees()

    # 3. Traitement + insertion des seuls fichiers pas encore traités
    traites, ignores = traiter_nouveaux_fichiers(DOSSIER_RAW)
    print(f"{traites} fichier(s) traité(s), {ignores} déjà traité(s) ignoré(s).")


if __name__ == "__main__":
    main()
