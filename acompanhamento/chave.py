"""Chave geral do módulo de acompanhamento."""

from django.conf import settings


def modulo_ativo() -> bool:
    """Diz se o módulo está ligado.

    Lê a configuração a cada chamada, e não na carga do módulo, para que os
    testes possam ligar e desligar a chave com override_settings.
    """
    return bool(getattr(settings, "ACOMPANHAMENTO_ATIVO", False))
