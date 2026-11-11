import argparse
import logging
import os
import subprocess
import time

import psycopg

from .config import BASE_DIR, DOSSIER_RAW, config_s3
from .generation_csv import generer_tous_les_csv
from .generation_images import generer_toutes_les_images
from .stockage_s3 import assurer_bucket, creer_client, envoyer_fichier
from .writing_postgres import traiter_nouveaux_fichiers

logger = logging.getLogger(__name__)


def lancer_services():
    """Démarre Postgres et le S3 local, et attend que leurs healthchecks soient OK."""
    subprocess.run(
        ["docker", "compose", "up", "-d", "db", "s3", "--wait"],
        cwd=BASE_DIR,
        check=True,
    )


def fabriquer_echec_insertion(nb_echecs: int):
    """Renvoie une fonction qui plante nb_echecs fois puis laisse passer (simulation de bug)."""
    compteur = {"restants": nb_echecs}

    def echouer():
        if compteur["restants"] > 0:
            compteur["restants"] -= 1
            raise psycopg.OperationalError("echec d'insertion simulé")

    return echouer


def traiter_depuis_s3() -> tuple[int, int]:
    """Traite les nouveaux fichiers du bucket. PIPELINE_ECHEC_INSERTION=n simule n échecs."""
    cfg = config_s3()
    client = creer_client()
    assurer_bucket(client, cfg["bucket"])
    nb_echecs = int(os.getenv("PIPELINE_ECHEC_INSERTION", "0"))
    hook = fabriquer_echec_insertion(nb_echecs) if nb_echecs else None
    return traiter_nouveaux_fichiers(client, cfg["bucket"], avant_commit=hook)


def lancer_pipeline_complete(avec_docker: bool = True):
    # 1. services (S3 + base)
    if avec_docker:
        lancer_services()

    # 2. génération des CSV et des images puis envoi dans le S3
    fichiers = generer_tous_les_csv(dossier_cible=str(DOSSIER_RAW))
    fichiers += generer_toutes_les_images(dossier_cible=str(DOSSIER_RAW))
    cfg = config_s3()
    client = creer_client()
    assurer_bucket(client, cfg["bucket"])
    for fichier in fichiers:
        envoyer_fichier(client, cfg["bucket"], fichier)
    print(f"{len(fichiers)} fichiers (csv et images) envoyés dans le bucket {cfg['bucket']}")

    # 3. traitement + insertion des fichiers pas encore traités
    traites, ignores = traiter_depuis_s3()
    print(f"{traites} fichier(s) traité(s), {ignores} déjà traité(s) ignoré(s).")


def lancer_worker(intervalle: int):
    """Boucle de production : regarde régulièrement si de nouveaux fichiers sont arrivés."""
    while True:
        try:
            traites, ignores = traiter_depuis_s3()
            print(f"{traites} fichier(s) traité(s), {ignores} ignoré(s).", flush=True)
        except Exception:
            # on ne tue pas le worker, le prochain passage réessaiera
            logger.exception("passage en erreur")
        time.sleep(intervalle)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Pipeline de transactions")
    parser.add_argument("--mode", choices=["complet", "worker"], default="complet")
    parser.add_argument("--sans-docker", action="store_true", help="services deja lances (CI)")
    parser.add_argument("--intervalle", type=int, default=60, help="secondes entre deux passages")
    args = parser.parse_args()

    if args.mode == "worker":
        lancer_worker(args.intervalle)
    else:
        lancer_pipeline_complete(avec_docker=not args.sans_docker)


if __name__ == "__main__":
    main()
