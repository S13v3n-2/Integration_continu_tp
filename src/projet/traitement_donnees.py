import glob
import pandas as pd
from collections import defaultdict
from decimal import Decimal

def read_transactions(path: str="data/raw/transactions_batch_*.csv"):
    # 1. Récupère la liste de tous les fichiers CSV correspondant au motif (pattern)
    fichiers_csv = glob.glob(path)

    # 2. Lit chaque fichier CSV et les stocke dans une liste de DataFrames
    liste_df = [pd.read_csv(fichier, sep=",") for fichier in fichiers_csv]

    # 3. Combine tous les DataFrames en un seul grand DataFrame
    df = pd.concat(liste_df, ignore_index=True)

    return df

def calculer_somme_par_iban_origine(df_transactions: pd.DataFrame) -> pd.DataFrame:
    """Calcule la somme des montants envoyés par IBAN d'origine à partir d'un DataFrame.
    Args:
        df_transactions: DataFrame Pandas contenant au moins 'iban_org' et 'montant'.
    Returns:
        DataFrame Pandas trié par montant décroissant.
    """
    
    if df_transactions.empty:
        return pd.DataFrame(columns=["iban_org", "montant_total"])

    # 1. Agrégation par 'iban_org' et somme de la colonne 'montant'
    df_sommes = (
        df_transactions.groupby("iban_org", as_index=False)["montant"]
        .sum()
        .rename(columns={"montant": "montant_total"})
    )

    # 2. Arrondi propre à 2 décimales pour les montants
    df_sommes["montant_total"] = df_sommes["montant_total"].round(2)

    # 3. Tri du plus grand au plus petit donneur d'ordre
    return df_sommes.sort_values(by="montant_total", ascending=False)



def calculer_somme_par_banque_src(df_transactions: pd.DataFrame) -> pd.DataFrame:
    if df_transactions.empty:
        return pd.DataFrame(columns=["banque_src", "montant_total"])

    # 1. Agrégation par 'banque_src' et somme de la colonne 'montant'
    df_sommes = (
        df_transactions.groupby("banque_src", as_index=False)["montant"]
        .sum()
        .rename(columns={"montant": "montant_total"})
    )

    # 2. Arrondi propre à 2 décimales pour les montants
    df_sommes["montant_total"] = df_sommes["montant_total"].round(2)

    # 3. Tri du plus grand au plus petit donneur d'ordre
    return df_sommes.sort_values(by="montant_total", ascending=False)


def calculer_somme_par_iban_dest(df_transactions: pd.DataFrame) -> pd.DataFrame:
    if df_transactions.empty:
        return pd.DataFrame(columns=["iban_dest", "montant_total"])

    # 1. Agrégation par 'iban_dest' et somme de la colonne 'montant'
    df_sommes = (
        df_transactions.groupby("iban_dest", as_index=False)["montant"]
        .sum()
        .rename(columns={"montant": "montant_total"})
    )

    # 2. Arrondi propre à 2 décimales pour les montants
    df_sommes["montant_total"] = df_sommes["montant_total"].round(2)

    # 3. Tri du plus grand au plus petit donneur d'ordre
    return df_sommes.sort_values(by="montant_total", ascending=False)


def calculer_flag_transaction_5000(df_transactions: pd.DataFrame) -> pd.DataFrame:
    if df_transactions.empty:
        return pd.DataFrame(columns=["montant"])

    # 1. Agrégation par 'iban_dest' et somme de la colonne 'montant'
    df_transactions_5000 = df_transactions.query("montant > 5000.00")

    # 3. Tri du plus grand au plus petit donneur d'ordre
    return df_transactions_5000


if __name__ == "__main__":
    # 1. Chargement de toutes les transactions
    df_raw = read_transactions("data/raw/transactions_batch_*.csv")

    # 2. Calcul des agrégations
    df_totaux_iban_org = calculer_somme_par_iban_origine(df_raw)
    
    # 3. Calcul des montants envoyés par banque source
    df_totaux_bank_org = calculer_somme_par_banque_src(df_raw)
    
    df_totaux_iban_dest = calculer_somme_par_iban_dest(df_raw)
    
    df_transactions_5000 = calculer_flag_transaction_5000(df_raw)

    # Affichage du résultat
    
    print("df_totaux_iban_org", df_totaux_iban_org.head())
    print("df_totaux_bank_org", df_totaux_bank_org.head())
    print("df_totaux_iban_dest", df_totaux_iban_dest.head())
    print("df_transactions_5000", df_transactions_5000.head())