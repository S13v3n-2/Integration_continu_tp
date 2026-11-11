# Pipeline de transactions financieres

Pipeline data : generation de CSV de transactions, stockage dans un S3 local (SeaweedFS),
traitement avec des fonctions pures (pandas) puis insertion dans PostgreSQL.

## Architecture

```
generation_csv.py ----+
                      +-> S3 (bucket transactions) -> traitement_donnees.py -> writing_postgres.py -> PostgreSQL
generation_images.py -+                                       ^
                                                          ocr.py (images)
```

- `generation_csv.py` : CSV deterministes (graine = numero de batch), 10 transactions par fichier.
- `generation_images.py` : images PNG de transactions (meme format de ligne que les CSV).
- `ocr.py` : lecture d'une image avec tesseract puis analyse du texte en transactions (analyse pure, tolerante aux erreurs de lecture).
- `stockage_s3.py` : envoi, liste et telechargement des fichiers (boto3), retry sur la recuperation.
- `traitement_donnees.py` : chargement d'un cote, fonctions pures de l'autre (somme par iban origine,
  par banque source, par iban destinataire, flag des montants > 5000).
- `writing_postgres.py` : schema, insertion et detection des fichiers deja traites.
- `pipeline.py` : orchestration (mode complet ou mode worker periodique).
- `retry.py` : decorateur de retry avec delai croissant.

### Base de donnees

| Table | Contenu |
|---|---|
| `fichiers_traites` | nom, hash sha256 et date de chaque fichier traite |
| `totaux_iban_org` | total envoye par iban d'origine |
| `totaux_banque_src` | total envoye par banque source |
| `totaux_iban_dest` | total recu par iban destinataire |
| `transactions_5000` | transactions strictement superieures a 5000 |

## Idempotence et retry

- Les resultats d'un fichier et son enregistrement dans `fichiers_traites` sont ecrits dans
  une seule transaction. En cas d'erreur, rien n'est ecrit et le retry repart de zero.
- `fichiers_traites` est unique sur le nom et sur le hash du contenu : un fichier deja traite
  (ou une copie sous un autre nom) est ignore, meme en cas de retry ou de deux workers en parallele.
- L'insertion est rejouee jusqu'a 4 fois (delai croissant). La recuperation S3 aussi.

## Lancer le projet

Un fichier `.env` est necessaire a la racine. Il se cree a partir de l'exemple fourni, puis on adapte les valeurs :

```
cp .env.example .env
```

Les variables sont decrites dans `.env.example` (base, S3, simulation d'un echec d'insertion).

```
pip install -r requirements-dev.txt
python -m src.projet.pipeline
```

La commande demarre Postgres et le S3 avec docker compose, genere les CSV, les envoie dans le S3,
puis traite ceux qui ne l'ont pas deja ete. Relancer la commande ne retraite rien.
Option `--sans-docker` si les services tournent deja.

## OCR (niveau 3)

Les fichiers `.png` du bucket sont lus avec tesseract puis traites comme les CSV : memes totaux,
meme idempotence. Une image illisible est signalee dans les logs, ne bloque pas les autres
fichiers et sera retentee au passage suivant.

Tesseract n'est pas installe sur la machine : il est dans l'image Docker (`Dockerfile`), le worker
et les tests l'utilisent depuis le conteneur.

## Tests

```
ruff check src tests
pytest -m "not integration"        # unitaires
docker compose up -d db s3 --wait
pytest -m integration              # necessite postgres et le S3
```

Les tests qui utilisent l'OCR sont ignores hors conteneur. Pour tout lancer, tesseract inclus :

```
docker compose --profile tests run --rm --build tests
```

Les tests d'integration creent une base et un bucket temporaires, les donnees locales ne sont pas touchees.

## Scenarios d'echec

### Bug dans le traitement

Dans `traitement_donnees.py`, remplacer `SEUIL_FLAG = 5000.00` par `SEUIL_FLAG = 50000.00`
(ou `>` par `>=` dans le flag). `pytest` echoue sur `test_flag_5000_exclut_le_seuil_exact` (valeurs ecrites a la main).
Le workflow CI passe au rouge sur GitHub.

### Bug d'insertion et retry

```
PIPELINE_ECHEC_INSERTION=2 python -m src.projet.pipeline --sans-docker
```

Les deux premieres insertions plantent avant le commit, les logs montrent les essais, la troisieme passe.
Les totaux en base restent corrects (pas de double comptage), verifie par
`test_retry_apres_echec_d_insertion_sans_double_comptage`.

## CI / CD

- `.github/workflows/ci.yml` : lint, tests unitaires puis tests d'integration (services Postgres et SeaweedFS, tesseract installe sur le runner).
- `.github/workflows/cd.yml` : apres une CI verte sur `main`, copie les fichiers sur la VM par SSH
  et lance `compose.prod.yml` (S3, base, worker).
  Secrets a definir : `VM_HOST`, `VM_USER`, `VM_SSH_KEY`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`.
- Le worker (`Dockerfile`) repasse toutes les 60 secondes sur le bucket pour traiter les nouveaux fichiers.
