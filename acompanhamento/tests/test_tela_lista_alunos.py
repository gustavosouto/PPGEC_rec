"""Tela de alunos por situação no marco e exportação para Excel."""

from datetime import date
from io import BytesIO

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from acompanhamento.lista_alunos import IRREGULARES, MARCO_INTERMEDIARIO
from acompanhamento.models import MarcoCalendario, PlanilhaBaixada
from acompanhamento.tests.test_lista_alunos import criar_aluno
from acompanhamento.tests.test_linha_de_base import criar_perfis


@override_settings(SECURE_SSL_REDIRECT=False, ACOMPANHAMENTO_ATIVO=True)
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
        self.assertContains(resposta, "Irregular")
        self.assertNotContains(resposta, "com chance")
        self.assertNotContains(resposta, "sem chance")
        self.assertContains(resposta, "Baixar em Excel")
        filtros = {
            filtro["titulo"]: filtro["valor"]
            for filtro in resposta.context["filtros_ativos"]
        }
        self.assertEqual(filtros["Situação no marco"], "Irregular")

    def test_opcoes_de_situacao_no_marco(self):
        resposta = self.client.get(self.endereco, {"marco": MARCO_INTERMEDIARIO})

        self.assertEqual(
            resposta.context["situacoes_marco"],
            (
                ("irregulares", "Irregular"),
                ("regular", "Regular"),
                ("cumprido", "Cumprido"),
                ("sem_prazo", "Sem prazo cadastrado"),
                ("nao_calculado", "Não foi possível calcular"),
            ),
        )

    @override_settings(ACOMPANHAMENTO_ATIVO=False)
    def test_parametros_de_marco_sao_ignorados_com_modulo_desligado(self):
        sem_parametros = self.client.get(self.endereco)
        com_marco = self.client.get(
            self.endereco,
            {
                "marco": MARCO_INTERMEDIARIO,
                "situacao_marco": "invalida",
                "semestre_marco": "2025-1",
                "exportar": "xlsx",
            },
        )

        self.assertEqual(sem_parametros.status_code, 200)
        self.assertEqual(com_marco.status_code, 200)
        self.assertEqual(
            [aluno.pk for aluno in sem_parametros.context["alunos"]],
            [aluno.pk for aluno in com_marco.context["alunos"]],
        )
        for campo in ("marco", "situacao_marco", "semestre_marco"):
            self.assertNotContains(com_marco, f'name="{campo}"')
        self.assertNotContains(com_marco, "Baixar em Excel")
        for coluna in (
            "Situação no marco",
            "Data limite",
            "Reapresentação até",
            "Semestre do marco",
            "Detalhe",
        ):
            self.assertNotContains(com_marco, coluna)
        self.assertNotEqual(
            com_marco["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def test_excel_contem_apenas_alunos_correspondentes_aos_filtros(self):
        inicio_download = timezone.now()
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
        self.assertEqual(linhas[1][8], "Irregular")
        self.assertEqual(len(linhas), 2)
        self.assertIn(
            f'alunos_por_marco_{MARCO_INTERMEDIARIO}_{timezone.localdate().isoformat()}.xlsx',
            resposta["Content-Disposition"],
        )
        registro = PlanilhaBaixada.objects.get()
        self.assertEqual(registro.baixada_por, self.perfis["servidor"])
        self.assertGreaterEqual(registro.baixada_em, inicio_download)
        self.assertLessEqual(registro.baixada_em, timezone.now())
        self.assertEqual(
            registro.filtros,
            {
                "nome": "Atrasado Tela Marco",
                "marco": MARCO_INTERMEDIARIO,
                "situacao_marco": IRREGULARES,
            },
        )

    def test_excel_grava_nome_iniciado_com_igual_como_texto(self):
        criar_aluno(
            "=1+1",
            prazo_qualificacao="2025.1",
            data_limite_qualificacao=date(2025, 6, 1),
        )

        resposta = self.client.get(
            self.endereco,
            {"nome": "=1+1", "marco": MARCO_INTERMEDIARIO, "exportar": "xlsx"},
        )

        self.assertEqual(resposta.status_code, 200)
        workbook = load_workbook(BytesIO(resposta.content))
        celula_nome = workbook.active["B2"]
        self.assertEqual(celula_nome.value, "=1+1")
        self.assertEqual(celula_nome.data_type, "s")

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
