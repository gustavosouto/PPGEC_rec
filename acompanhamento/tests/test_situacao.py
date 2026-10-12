"""Testes dos 19 casos de prazo da tabela (Anexo A.1 a A.3).

Cada teste é um caso da tabela, na mesma ordem. Enquanto a regra não
está programada em situacao.py, eles falham: é o esperado.
"""

from datetime import date

from django.test import SimpleTestCase

from acompanhamento.situacao import (
    CUMPRIDO,
    DOUTORADO,
    FORA_DO_CALCULO,
    IRREGULAR_COM_CHANCE,
    IRREGULAR_SEM_CHANCE,
    MESTRADO,
    REGULAR,
    SEM_PRAZO,
    Apresentacao,
    calcular_situacao_defesa,
    calcular_situacao_marco,
)


def marco(nivel, data_limite, apresentacoes, referencia, concluido=False):
    return calcular_situacao_marco(
        nivel=nivel,
        data_limite=data_limite,
        apresentacoes=apresentacoes,
        data_referencia=referencia,
        concluido_marcado=concluido,
    )


def defesa(nivel, ingresso, prorrogacao, referencia, defendeu=False):
    return calcular_situacao_defesa(
        nivel=nivel,
        mes_ingresso=ingresso,
        prorrogacao_meses=prorrogacao,
        data_referencia=referencia,
        defesa_registrada=defendeu,
    )


class ProjetoDissertacaoTests(SimpleTestCase):
    """Casos 1 a 10 (mestrado)."""

    LIMITE = date(2026, 9, 20)

    def test_caso_01_antes_da_data_limite_e_regular(self):
        r = marco(MESTRADO, self.LIMITE, [], date(2026, 9, 1))
        self.assertEqual(r.situacao, REGULAR)

    def test_caso_02_aprovado_com_conceito_a_e_cumprido(self):
        r = marco(
            MESTRADO,
            self.LIMITE,
            [Apresentacao(date(2026, 9, 18), "A")],
            date(2026, 11, 1),
        )
        self.assertEqual(r.situacao, CUMPRIDO)

    def test_caso_03_nao_apresentou_tem_chance_de_reapresentar(self):
        r = marco(MESTRADO, self.LIMITE, [], date(2026, 11, 1))
        self.assertEqual(r.situacao, IRREGULAR_COM_CHANCE)
        self.assertEqual(r.prazo_reapresentacao, date(2026, 12, 20))

    def test_caso_04_passou_o_prazo_da_reapresentacao_sem_chance(self):
        r = marco(MESTRADO, self.LIMITE, [], date(2026, 12, 21))
        self.assertEqual(r.situacao, IRREGULAR_SEM_CHANCE)

    def test_caso_05_conceito_c_tem_chance_de_repetir(self):
        r = marco(
            MESTRADO,
            self.LIMITE,
            [Apresentacao(date(2026, 9, 15), "C")],
            date(2026, 11, 1),
        )
        self.assertEqual(r.situacao, IRREGULAR_COM_CHANCE)
        self.assertEqual(r.prazo_reapresentacao, date(2026, 12, 15))

    def test_caso_06_segundo_conceito_c_fica_sem_chance(self):
        r = marco(
            MESTRADO,
            self.LIMITE,
            [
                Apresentacao(date(2026, 9, 15), "C"),
                Apresentacao(date(2026, 12, 10), "C"),
            ],
            date(2026, 12, 11),
        )
        self.assertEqual(r.situacao, IRREGULAR_SEM_CHANCE)

    def test_caso_07_primeira_apresentacao_apos_o_limite_e_a_reapresentacao(self):
        r = marco(
            MESTRADO,
            self.LIMITE,
            [Apresentacao(date(2026, 11, 15), "C")],
            date(2026, 11, 16),
        )
        self.assertEqual(r.situacao, IRREGULAR_SEM_CHANCE)

    def test_caso_08_aprovado_na_reapresentacao_e_cumprido(self):
        r = marco(
            MESTRADO,
            self.LIMITE,
            [Apresentacao(date(2026, 11, 15), "A")],
            date(2026, 11, 16),
        )
        self.assertEqual(r.situacao, CUMPRIDO)

    def test_caso_09_marcacao_concluido_sem_apresentacao_e_cumprido_com_aviso(self):
        r = marco(MESTRADO, self.LIMITE, [], date(2026, 11, 1), concluido=True)
        self.assertEqual(r.situacao, CUMPRIDO)
        self.assertTrue(r.avisos)

    def test_caso_10_sem_data_limite_e_sem_prazo(self):
        r = marco(MESTRADO, None, [], date(2026, 11, 1))
        self.assertEqual(r.situacao, SEM_PRAZO)


class QualificacaoTests(SimpleTestCase):
    """Casos 11 a 13 (doutorado). Prazo de reapresentação: 6 meses."""

    SESSAO = date(2028, 6, 7)

    def test_caso_11_nao_apresentou_tem_6_meses_para_reapresentar(self):
        r = marco(DOUTORADO, self.SESSAO, [], date(2028, 9, 1))
        self.assertEqual(r.situacao, IRREGULAR_COM_CHANCE)
        self.assertEqual(r.prazo_reapresentacao, date(2028, 12, 7))

    def test_caso_12_conceito_c_na_sessao_tem_6_meses_para_repetir(self):
        r = marco(
            DOUTORADO,
            self.SESSAO,
            [Apresentacao(self.SESSAO, "C")],
            date(2028, 9, 1),
        )
        self.assertEqual(r.situacao, IRREGULAR_COM_CHANCE)
        self.assertEqual(r.prazo_reapresentacao, date(2028, 12, 7))

    def test_caso_13_sem_data_da_sessao_e_sem_prazo(self):
        r = marco(DOUTORADO, None, [], date(2028, 9, 1))
        self.assertEqual(r.situacao, SEM_PRAZO)


class DefesaTests(SimpleTestCase):
    """Casos 14 a 19."""

    def test_caso_14_mestrado_dentro_do_prazo_e_regular(self):
        r = defesa(MESTRADO, date(2025, 3, 1), 0, date(2027, 3, 15))
        self.assertEqual(r.situacao, REGULAR)
        self.assertEqual(r.data_limite, date(2027, 3, 31))

    def test_caso_15_prorrogacao_estende_o_limite(self):
        r = defesa(MESTRADO, date(2025, 3, 1), 3, date(2027, 5, 15))
        self.assertEqual(r.situacao, REGULAR)
        self.assertEqual(r.data_limite, date(2027, 6, 30))

    def test_caso_16_passou_do_limite_sem_defesa_fica_sem_chance(self):
        r = defesa(MESTRADO, date(2025, 3, 1), 0, date(2027, 4, 1))
        self.assertEqual(r.situacao, IRREGULAR_SEM_CHANCE)

    def test_caso_17_prorrogacao_mantem_o_dia_do_mes(self):
        r = defesa(MESTRADO, date(2025, 2, 1), 3, date(2027, 5, 20))
        self.assertEqual(r.situacao, REGULAR)
        self.assertEqual(r.data_limite, date(2027, 5, 28))

    def test_caso_18_doutorado_tem_48_meses(self):
        r = defesa(DOUTORADO, date(2026, 3, 1), 0, date(2030, 1, 1))
        self.assertEqual(r.situacao, REGULAR)
        self.assertEqual(r.data_limite, date(2030, 3, 31))

    def test_caso_19_quem_defendeu_sai_do_calculo(self):
        r = defesa(
            MESTRADO, date(2025, 3, 1), 0, date(2030, 1, 1), defendeu=True
        )
        self.assertEqual(r.situacao, FORA_DO_CALCULO)
        