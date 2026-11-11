import pytest

from src.projet.retry import avec_retry


@pytest.fixture(autouse=True)
def sans_attente(monkeypatch):
    monkeypatch.setattr("src.projet.retry.time.sleep", lambda _: None)


def test_reussit_apres_quelques_echecs():
    appels = []

    @avec_retry(tentatives=3, exceptions=(ValueError,))
    def fragile():
        appels.append(1)
        if len(appels) < 3:
            raise ValueError("pas encore")
        return "ok"

    assert fragile() == "ok"
    assert len(appels) == 3


def test_leve_l_erreur_apres_la_derniere_tentative():
    appels = []

    @avec_retry(tentatives=3, exceptions=(ValueError,))
    def toujours_ko():
        appels.append(1)
        raise ValueError("ko")

    with pytest.raises(ValueError):
        toujours_ko()
    assert len(appels) == 3


def test_ne_rejoue_pas_les_autres_exceptions():
    appels = []

    @avec_retry(tentatives=3, exceptions=(ValueError,))
    def mauvaise_erreur():
        appels.append(1)
        raise KeyError("autre")

    with pytest.raises(KeyError):
        mauvaise_erreur()
    assert len(appels) == 1
