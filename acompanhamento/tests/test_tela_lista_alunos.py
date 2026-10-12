"""Tela de alunos por situação no marco e exportação para Excel."""

from datetime import date
from io import BytesIO

from django.test import TestCase, override_settings
from django.urls import reverse
from openpyxl import load_workbook

from acompanhamento.lista_alunos import IRREGULARES, MARCO_INTERMEDIARIO
from acompanhamento.models import MarcoCalendario
from acompanhamento.tests.test_lista_alunos import criar_aluno
from acompanhamento.tests.test_linha_de_base import criar_perfis


@override_settings(SECURE_SSL_REDIRECT=False)
class TelaListaAlunosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.perfis = criar_perfis()
        cls.endereco = reverse("coordenacao_alunos")
        MarcoCalendario.objects.create(
            semestre="2025.1",
            tipo=MarcoCalendario.TipoMarco.PROJETO_DISSERTACAO,
            data_limite=date(2025, 6, 1),
        )
        criar_aluno(
            "Atrasado Tela Marco",
            prazo_qualificacao="2025.1",
            data_limite_qualificacao=date(2025, 6, 1),
        )

    def setUp(self):
        self.client.force_login(self.perfis["servidor"])

    def test_lista_filtrada_exibe_situacao_e_botao_excel(self):
        resposta = self.client.get(
            self.endereco,
            {
                "nome": "Atrasado Tela Marco",
                "marco": MARCO_INTERMEDIARIO,
                "situacao_marco": IRREGULARES,
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Atrasado Tela Marco")
        self.assertContains(resposta, "Irregular sem chance")
        self.assertContains(resposta, "Baixar em Excel")

    def test_excel_contem_apenas_alunos_correspondentes_aos_filtros(self):
        resposta = self.client.get(
            self.endereco,
            {
                "nome": "Atrasado Tela Marco",
                "marco": MARCO_INTERMEDIARIO,
                "situacao_marco": IRREGULARES,
                "exportar": "xlsx",
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            resposta["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        workbook = load_workbook(BytesIO(resposta.content), read_only=True)
        linhas = list(workbook.active.values)

        self.assertEqual(linhas[0][1], "Nome")
        self.assertEqual(linhas[1][1], "Atrasado Tela Marco")
        self.assertEqual(linhas[1][8], "Irregular sem chance")
        self.assertEqual(len(linhas), 2)

    def test_filtro_de_semestre_invalido_exibe_erro(self):
        resposta = self.client.get(
            self.endereco,
            {
                "marco": MARCO_INTERMEDIARIO,
                "semestre_marco": "2025-1",
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Semestre do marco inválido.")
