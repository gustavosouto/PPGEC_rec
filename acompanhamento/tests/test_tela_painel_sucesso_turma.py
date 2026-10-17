from django.test import TestCase, override_settings
from django.urls import reverse

from acompanhamento.tests.test_linha_de_base import criar_perfis


@override_settings(ACOMPANHAMENTO_ATIVO=True, SECURE_SSL_REDIRECT=False)
class TelaPainelSucessoTurmaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.perfis = criar_perfis()
        cls.url = reverse("acompanhamento:painel_sucesso_turma")

    def test_acesso_tela_sucesso_turma(self):
        """Garante acesso à tela do painel de sucesso por turma."""
        self.client.force_login(self.perfis["membro_secretaria"])
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        