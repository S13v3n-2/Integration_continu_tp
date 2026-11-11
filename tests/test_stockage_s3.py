import pytest
from botocore.exceptions import EndpointConnectionError

from src.projet.stockage_s3 import telecharger_contenu


class FauxClient:
    """Client S3 qui échoue un nombre donné de fois avant de répondre."""

    def __init__(self, nb_echecs):
        self.nb_echecs = nb_echecs
        self.appels = 0

    def get_object(self, Bucket, Key):
        self.appels += 1
        if self.appels <= self.nb_echecs:
            raise EndpointConnectionError(endpoint_url="http://s3-down")
        return {"Body": type("Corps", (), {"read": lambda self: b"a,b\n1,2\n"})()}


@pytest.fixture(autouse=True)
def sans_attente(monkeypatch):
    monkeypatch.setattr("src.projet.retry.time.sleep", lambda _: None)


def test_telechargement_reessaye_si_le_s3_ne_repond_pas():
    client = FauxClient(nb_echecs=2)
    assert telecharger_contenu(client, "b", "f.csv") == b"a,b\n1,2\n"
    assert client.appels == 3


def test_telechargement_abandonne_apres_les_tentatives():
    client = FauxClient(nb_echecs=99)
    with pytest.raises(EndpointConnectionError):
        telecharger_contenu(client, "b", "f.csv")
    assert client.appels == 4
