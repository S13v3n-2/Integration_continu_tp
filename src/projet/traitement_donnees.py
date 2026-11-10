import glob
import io

import pandas as pd

SEUIL_FLAG = 5000.00


# Chargement des données (effets de bord : lecture de fichiers)

def read_transactions(path: str = "data/raw/transactions_batch_*.csv") -> pd.DataFrame:
    """Lit tous les CSV qui correspondent au motif et les regroupe dans un DataFrame."""
    fichiers_csv = sorted(glob.glob(path))
    if not fichiers_csv:
        return pd.DataFrame()
    return pd.concat([pd.read_csv(f) for f in fichiers_csv], ignore_index=True)


def lire_transactions_bytes(contenu: bytes) -> pd.DataFrame:
    """Construit un DataFrame à partir du contenu brut d'un CSV (ex: récupéré sur S3)."""
    return pd.read_csv(io.BytesIO(contenu))


# Fonctions de traitement (pures : pas d'IO, le DataFrame d'entrée n'est pas modifié)

def _somme_par(df_transactions: pd.DataFrame, cle: str) -> pd.DataFrame:
    if df_transactions.empty:
        return pd.DataFrame(columns=[cle, "montant_total"])

    df_sommes = (
        df_transactions.groupby(cle, as_index=False)["montant"]
        .sum()
        .rename(columns={"montant": "montant_total"})
    )
    df_sommes["montant_total"] = df_sommes["montant_total"].round(2)
    return df_sommes.sort_values(by="montant_total", ascending=False)


def calculer_somme_par_iban_origine(df_transactions: pd.DataFrame) -> pd.DataFrame:
    """Somme des montants envoyés par iban d'origine, triée par montant décroissant."""
    return _somme_par(df_transactions, "iban_org")


def calculer_somme_par_banque_src(df_transactions: pd.DataFrame) -> pd.DataFrame:
    """Somme des montants envoyés par banque source, triée par montant décroissant."""
    return _somme_par(df_transactions, "banque_src")


def calculer_somme_par_iban_dest(df_transactions: pd.DataFrame) -> pd.DataFrame:
    """Somme des montants reçus par iban destinataire, triée par montant décroissant."""
    return _somme_par(df_transactions, "iban_dest")


def calculer_flag_transaction_5000(df_transactions: pd.DataFrame) -> pd.DataFrame:
    """Garde les transactions strictement au dessus de 5000, triées par montant décroissant."""
    if df_transactions.empty:
        return pd.DataFrame(columns=df_transactions.columns)

    df_flag = df_transactions[df_transactions["montant"] > SEUIL_FLAG]
    return df_flag.sort_values(by="montant", ascending=False)


if __name__ == "__main__":
    df_raw = read_transactions()
    print(calculer_somme_par_iban_origine(df_raw).head())
    print(calculer_somme_par_banque_src(df_raw).head())
    print(calculer_somme_par_iban_dest(df_raw).head())
    print(calculer_flag_transaction_5000(df_raw).head())
