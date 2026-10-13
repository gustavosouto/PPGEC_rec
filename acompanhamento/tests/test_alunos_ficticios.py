"""Confere a situação de cada aluno gerado por gerar_dados_ficticios.

Os alunos são identificados pela ordem de criação (pk da trajetória), que
segue a ordem do comando. Se o comando mudar essa ordem, a tabela ESPERADO
precisa mudar junto.
"""

from datetime import date

from django.core.management import call_command
from django.test import TestCase, override_settings

from acompanhamento.situacao import (
    CUMPRIDO,
    FORA_DO_CALCULO,
    IRREGULAR_COM_CHANCE,
    IRREGULAR_SEM_CHANCE,
    MESTRADO,
    REGULAR,
    SEM_PRAZO,
    calcular_situacao_defesa,
    calcular_situacoes,
)
from processos.models import TrajetoriaAcademica

REFERENCIA = date(2026, 10, 12)

# (número, nível, status, situação no marco, situação na defesa, cenário)
ESPERADO = [
    (1, "MESTRADO", "ATIVA", REGULAR, REGULAR, "mestrado em dia"),
    (2, "MESTRADO", "ATIVA", IRREGULAR_COM_CHANCE, REGULAR,
     "projeto atrasado, com chance"),
    (3, "MESTRADO", "ATIVA", IRREGULAR_SEM_CHANCE, REGULAR,
     "projeto atrasado, sem chance"),
    (4, "MESTRADO", "ATIVA", SEM_PRAZO, SEM_PRAZO, "sem datas cadastradas"),
    (5, "MESTRADO", "ATIVA", IRREGULAR_SEM_CHANCE, IRREGULAR_SEM_CHANCE,
     "projeto e defesa vencidos"),
    (6, "MESTRADO", "CONCLUIDA", CUMPRIDO, FORA_DO_CALCULO, "já defendeu"),
    (7, "MESTRADO", "ATIVA", CUMPRIDO, REGULAR,
     "projeto aprovado antes do limite"),
    (8, "MESTRADO", "ATIVA", IRREGULAR_SEM_CHANCE, REGULAR,
     "apresentou depois do limite com conceito C"),
    (9, "MESTRADO", "ATIVA", IRREGULAR_COM_CHANCE, REGULAR,
     "defesa salva por prorrogação e trancamento"),
    # O cálculo não filtra por status: trancado e desligado saem calculados.
    # Quem os tira da lista é a tela de alunos, não o cálculo.
    (10, "MESTRADO", "TRANCADA", IRREGULAR_SEM_CHANCE, REGULAR,
     "trancado, atrasado no projeto"),
    (11, "MESTRADO", "DESLIGADA", IRREGULAR_SEM_CHANCE, REGULAR,
     "desligado, atrasado no projeto"),
    (12, "DOUTORADO", "ATIVA", CUMPRIDO, REGULAR,
     "doutorado qualificado, em dia"),
    (13, "DOUTORADO", "ATIVA", CUMPRIDO, IRREGULAR_SEM_CHANCE,
     "doutorado qualificado, defesa vencida"),
    (14, "DOUTORADO", "ATIVA", IRREGULAR_COM_CHANCE, REGULAR,
     "qualificação atrasada, com chance"),
]


@override_settings(DEBUG=True)
class AlunosFicticiosSituacaoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command(
            "gerar_dados_ficticios",
            data_referencia=REFERENCIA,
            verbosity=0,
        )
        cls.trajetorias = list(
            TrajetoriaAcademica.objects.filter(
                aluno__email__endswith="@ficticio.invalid"
            ).order_by("pk")
        )
        cls.resultados = calcular_situacoes(cls.trajetorias, REFERENCIA)

    def test_gera_as_14_trajetorias(self):
        self.assertEqual(len(self.trajetorias), len(ESPERADO))

    def test_cada_aluno_cai_na_situacao_esperada(self):
        for numero, nivel, status, marco, defesa, cenario in ESPERADO:
            with self.subTest(aluno=numero, cenario=cenario):
                trajetoria = self.trajetorias[numero - 1]
                resultado = self.resultados[trajetoria.pk]
                self.assertEqual(trajetoria.nivel_curso, nivel)
                self.assertEqual(trajetoria.status, status)
                self.assertEqual(resultado["marco"].situacao, marco)
                self.assertEqual(resultado["defesa"].situacao, defesa)

    def test_as_cinco_situacoes_aparecem_no_marco(self):
        no_marco = {r["marco"].situacao for r in self.resultados.values()}
        cinco = {
            REGULAR,
            IRREGULAR_COM_CHANCE,
            IRREGULAR_SEM_CHANCE,
            CUMPRIDO,
            SEM_PRAZO,
        }
        self.assertTrue(cinco <= no_marco, f"faltam: {cinco - no_marco}")

    def test_todo_resultado_traz_motivo_em_portugues(self):
        for pk, resultado in self.resultados.items():
            for parte in ("marco", "defesa"):
                with self.subTest(trajetoria=pk, parte=parte):
                    self.assertTrue(resultado[parte].motivo.strip())

    def test_prorrogacao_e_trancamento_estendem_o_prazo_da_defesa(self):
        trajetoria = self.trajetorias[8]
        defesa = self.resultados[trajetoria.pk]["defesa"]

        # prazo regimental 30/09/2026 + 3 meses + 30 dias de trancamento
        self.assertEqual(defesa.data_limite, date(2027, 1, 29))

        # sem as extensões, o mesmo aluno estaria atrasado
        sem_extensoes = calcular_situacao_defesa(
            nivel=MESTRADO,
            mes_ingresso=trajetoria.data_ingresso,
            prorrogacao_meses=0,
            data_referencia=REFERENCIA,
        )
        self.assertEqual(sem_extensoes.situacao, IRREGULAR_SEM_CHANCE)
