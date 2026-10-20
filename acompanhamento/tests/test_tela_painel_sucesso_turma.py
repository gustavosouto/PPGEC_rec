from django.test import TestCase, override_settings
from django.urls import reverse

from acompanhamento.tests.test_linha_de_base import criar_perfis


class TelaPainelSucessoTurmaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.perfis = criar_perfis()
        cls.url = reverse("acompanhamento:painel_sucesso_turma")

    @override_settings(ACOMPANHAMENTO_ATIVO=False)
    def test_chave_desligada_retorna_404(self):
        """Garante que a rota responde 404 quando o módulo está inativo."""
        self.client.force_login(self.perfis["membro_secretaria"])
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    @override_settings(ACOMPANHAMENTO_ATIVO=True, SECURE_SSL_REDIRECT=False)
    def test_aluno_nao_pode_acessar_tela(self):
        """Garante que perfis não autorizados (ex: aluno) recebem 403."""
        self.client.force_login(self.perfis["aluno"])
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    @override_settings(ACOMPANHAMENTO_ATIVO=True)
    def test_gestao_consegue_acessar_tela(self):
        """Garante que membros da gestão conseguem acessar o painel."""
        self.client.force_login(self.perfis["membro_secretaria"])
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    @override_settings(ACOMPANHAMENTO_ATIVO=True, SECURE_SSL_REDIRECT=False)
    def test_filtro_nivel_selecionado_e_nivel_invalido(self):
        """Garante que o nível selecionado é mantido e níveis inválidos caem em TODOS."""
        self.client.force_login(self.perfis["membro_secretaria"])

        response = self.client.get(self.url, {"nivel": "MESTRADO"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["nivel_selecionado"], "MESTRADO")

        response_invalido = self.client.get(self.url, {"nivel": "INVALIDO"})
        self.assertEqual(response_invalido.status_code, 200)
        self.assertEqual(response_invalido.context["nivel_selecionado"], "TODOS")

    @override_settings(ACOMPANHAMENTO_ATIVO=True, SECURE_SSL_REDIRECT=False)
    def test_tela_listada_na_pagina_inicial_do_modulo(self):
        """Garante que a nova tela está registrada e visível na página inicial do módulo."""
        self.client.force_login(self.perfis["membro_secretaria"])
        response = self.client.get(reverse("acompanhamento:acompanhamento_inicio"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.url)
