import functools
import logging
import time

logger = logging.getLogger(__name__)


def avec_retry(tentatives: int = 3, delai: float = 1.0, exceptions: tuple = (Exception,)):
    """Relance la fonction si elle lève une des exceptions données.

    Le délai double à chaque nouvel essai. Après la dernière tentative,
    l'exception d'origine est relevée.
    """

    def decorateur(fonction):
        @functools.wraps(fonction)
        def enveloppe(*args, **kwargs):
            attente = delai
            for essai in range(1, tentatives + 1):
                try:
                    return fonction(*args, **kwargs)
                except exceptions as erreur:
                    if essai == tentatives:
                        raise
                    logger.warning(
                        "%s a échoué (essai %d/%d) : %s",
                        fonction.__name__, essai, tentatives, erreur,
                    )
                    time.sleep(attente)
                    attente *= 2

        return enveloppe

    return decorateur
