"""Tela do painel de processos: acesso, escolha do semestre e estados vazios."""

from django.test import TestCase, override_settings
from django.urls import reverse

from acompanhamento.tests.test_fundacao import PERFIS_COM_GESTAO
from acompanhamento.tests.test_linha_de_base import criar_perfis


@override_settings(ACOMPANHAMENTO_ATIVO=True, SECURE_SSL_REDIRECT=False)
class TelaPainelProcessosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.perfis = criar_perfis()
        cls.endereco = reverse("acompanhamento:painel_processos")

    def test_acesso_por_perfil(self):
        for nome, usuario in self.perfis.items():
            with self.subTest(perfil=nome):
                self.client.force_login(usuario)
                esperado = 200 if nome in PERFIS_COM_GESTAO else 403
                self.assertEqual(self.client.get(self.endereco).status_code, esperado)

    @override_settings(ACOMPANHAMENTO_ATIVO=False)
    def test_chave_desligada_responde_como_pagina_inexistente(self):
        self.client.force_login(self.perfis["membro_secretaria"])
        self.assertEqual(self.client.get(self.endereco).status_code, 404)

    def test_semestre_escolhido_aparece_selecionado(self):
        self.client.force_login(self.perfis["membro_secretaria"])
        resposta = self.client.get(self.endereco, {"semestre": "2001.1"})
        self.assertContains(resposta, "Processos abertos no semestre 2001.1.")
        self.assertContains(resposta, '<option value="2001.1" selected>', html=False)

    def test_semestre_invalido_avisa_e_mostra_o_semestre_atual(self):
        self.client.force_login(self.perfis["membro_secretaria"])
        resposta = self.client.get(self.endereco, {"semestre": "2026-2"}, follow=True)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Semestre inválido. Use o formato AAAA.1 ou AAAA.2.")

    def test_semestre_sem_processos_mostra_estados_vazios(self):
        self.client.force_login(self.perfis["membro_secretaria"])
        resposta = self.client.get(self.endereco, {"semestre": "2001.1"})
        self.assertContains(resposta, "Nenhum processo finalizado no semestre")
        self.assertContains(resposta, "Nenhum processo aberto no semestre.")
        self.assertContains(resposta, "01/2001")

    def test_tela_listada_na_pagina_inicial_do_modulo(self):
        self.client.force_login(self.perfis["membro_secretaria"])
        resposta = self.client.get(reverse("acompanhamento:acompanhamento_inicio"))
        self.assertContains(resposta, self.endereco)
