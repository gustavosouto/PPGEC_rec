from django.test import TestCase, override_settings
from django.core import mail

from acompanhamento.tasks import enviar_avisos_irregularidade

SEM_AVISO = {"avisos_novos": 0, "emails_enviados": 0}


class ChaveDoAvisoTests(TestCase):
    def _nao_faz_nada(self):
        with self.assertNumQueries(0):
            resultado = enviar_avisos_irregularidade()
        self.assertEqual(resultado, SEM_AVISO)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(ACOMPANHAMENTO_ATIVO=True, ACOMPANHAMENTO_AVISO_ATIVO=False)
    def test_aviso_desligado_nao_consulta_o_banco(self):
        self._nao_faz_nada()

    @override_settings(ACOMPANHAMENTO_ATIVO=False, ACOMPANHAMENTO_AVISO_ATIVO=True)
    def test_modulo_desligado_nao_consulta_o_banco(self):
        self._nao_faz_nada()

    @override_settings(ACOMPANHAMENTO_ATIVO=False, ACOMPANHAMENTO_AVISO_ATIVO=False)
    def test_os_dois_desligados_nao_consultam_o_banco(self):
        self._nao_faz_nada()