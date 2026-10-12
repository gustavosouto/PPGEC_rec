"""Regra de situação do aluno em cada marco.

Projeto de dissertação (mestrado) e qualificação (doutorado): a data
limite é a da sessão. Quem não apresenta até ela tem uma única nova
chance, em 3 meses (mestrado) ou 6 meses (doutorado). A defesa fica
para a próxima etapa (calcular_situacao_defesa).
"""

import calendar
from dataclasses import dataclass, field, replace
from datetime import date

REGULAR = "regular"
IRREGULAR_COM_CHANCE = "irregular_com_chance"
IRREGULAR_SEM_CHANCE = "irregular_sem_chance"
CUMPRIDO = "cumprido"
SEM_PRAZO = "sem_prazo"
FORA_DO_CALCULO = "fora_do_calculo"

MESTRADO = "mestrado"
DOUTORADO = "doutorado"

ORIGEM_TRAJETORIA = "trajetoria"
ORIGEM_CALENDARIO = "calendario"

MESES_REAPRESENTACAO = {MESTRADO: 3, DOUTORADO: 6}
CONCEITOS_APROVADOS = ("A", "B")


@dataclass(frozen=True)
class Apresentacao:
    data: date
    conceito: str


@dataclass(frozen=True)
class Resultado:
    situacao: str
    data_limite: date | None = None
    prazo_reapresentacao: date | None = None
    motivo: str = ""
    avisos: list = field(default_factory=list)
    origem_data_limite: str = ""


def somar_meses(data, meses):
    """Soma meses mantendo o dia; se o mês não tem o dia, usa o último."""
    indice = data.year * 12 + (data.month - 1) + meses
    ano, mes = divmod(indice, 12)
    mes += 1
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    return date(ano, mes, min(data.day, ultimo_dia))


def _formatar(data):
    return data.strftime("%d/%m/%Y")


def calcular_situacao_marco(
    nivel,
    data_limite,
    apresentacoes,
    data_referencia,
    concluido_marcado=False,
):
    """Projeto de dissertação (mestrado) ou qualificação (doutorado)."""
    meses = MESES_REAPRESENTACAO[nivel]
    feitas = sorted(
        (a for a in apresentacoes if a.data <= data_referencia),
        key=lambda a: a.data,
    )
    aprovada = any(a.conceito.strip().upper() in CONCEITOS_APROVADOS for a in feitas)

    if aprovada or concluido_marcado:
        avisos = []
        if not aprovada:
            avisos.append(
                "Marcação de projeto/qualificação concluído sem apresentação "
                "aprovada registrada. Conferir o cadastro."
            )
        elif not concluido_marcado:
            avisos.append(
                "Apresentação aprovada registrada, mas a trajetória não está "
                "marcada como projeto/qualificação concluído. Conferir o cadastro."
            )
        return Resultado(
            CUMPRIDO,
            data_limite=data_limite,
            motivo="Marco cumprido.",
            avisos=avisos,
        )

    if data_limite is None:
        return Resultado(
            SEM_PRAZO,
            motivo="Não há data limite cadastrada para o semestre do marco.",
        )

    if any(a.conceito.strip().upper() == "D" for a in feitas):
        return Resultado(
            IRREGULAR_SEM_CHANCE,
            data_limite=data_limite,
            motivo="Reprovado com conceito D.",
        )

    if not feitas:
        if data_referencia <= data_limite:
            return Resultado(
                REGULAR,
                data_limite=data_limite,
                motivo=f"Data limite em {_formatar(data_limite)}.",
            )
        prazo = somar_meses(data_limite, meses)
        if data_referencia <= prazo:
            return Resultado(
                IRREGULAR_COM_CHANCE,
                data_limite=data_limite,
                prazo_reapresentacao=prazo,
                motivo=(
                    f"Não apresentou até {_formatar(data_limite)}. "
                    f"Reapresentação até {_formatar(prazo)}."
                ),
            )
        return Resultado(
            IRREGULAR_SEM_CHANCE,
            data_limite=data_limite,
            prazo_reapresentacao=prazo,
            motivo=(
                f"Não apresentou até {_formatar(data_limite)} nem na "
                f"reapresentação, que ia até {_formatar(prazo)}."
            ),
        )

    primeira = feitas[0]

    if primeira.data > data_limite:
        return Resultado(
            IRREGULAR_SEM_CHANCE,
            data_limite=data_limite,
            motivo=(
                f"Apresentou depois da data limite ({_formatar(data_limite)}), "
                "na reapresentação, e não foi aprovado."
            ),
        )

    if len(feitas) > 1:
        return Resultado(
            IRREGULAR_SEM_CHANCE,
            data_limite=data_limite,
            motivo="Não foi aprovado na repetição, que era a última chance.",
        )

    prazo = somar_meses(primeira.data, meses)
    if data_referencia <= prazo:
        return Resultado(
            IRREGULAR_COM_CHANCE,
            data_limite=data_limite,
            prazo_reapresentacao=prazo,
            motivo=(
                f"Conceito C em {_formatar(primeira.data)}. "
                f"Repetição até {_formatar(prazo)}."
            ),
        )
    return Resultado(
        IRREGULAR_SEM_CHANCE,
        data_limite=data_limite,
        prazo_reapresentacao=prazo,
        motivo=(
            f"Conceito C em {_formatar(primeira.data)} e a repetição, "
            f"que ia até {_formatar(prazo)}, não aconteceu."
        ),
    )


def calcular_situacao_defesa(
    nivel,
    mes_ingresso,
    prorrogacao_meses,
    data_referencia,
    defesa_registrada=False,
):
    """Defesa: limite efetivo = prazo regimental + prorrogações."""
    raise NotImplementedError


def resolver_data_limite(trajetoria):
    """Data limite do marco intermediário do aluno e de onde ela veio.

    Mestrado: vale a "Data limite do projeto" da trajetória, se preenchida;
    senão, a data do calendário para o semestre do projeto. Doutorado: vale
    a data do calendário para o quinto semestre. Sem nenhuma das duas,
    devolve (None, "").
    """
    from acompanhamento.models import MarcoCalendario

    if trajetoria.nivel_curso == "MESTRADO":
        if trajetoria.data_limite_qualificacao:
            return trajetoria.data_limite_qualificacao, ORIGEM_TRAJETORIA
        semestre = trajetoria.prazo_qualificacao
        tipo = MarcoCalendario.TipoMarco.PROJETO_DISSERTACAO
    elif trajetoria.nivel_curso == "DOUTORADO":
        semestre = (
            trajetoria.prazo_qualificacao or trajetoria.prazo_qualificacao_regimental
        )
        tipo = MarcoCalendario.TipoMarco.QUALIFICACAO
    else:
        return None, ""

    if not semestre:
        return None, ""
    data = MarcoCalendario.data_limite_do(semestre, tipo)
    return (data, ORIGEM_CALENDARIO) if data else (None, "")


def calcular_situacao_trajetoria(trajetoria, data_referencia):
    """Situação de uma trajetória no projeto/qualificação, lendo o cadastro."""
    nivel = MESTRADO if trajetoria.nivel_curso == "MESTRADO" else DOUTORADO
    data_limite, origem = resolver_data_limite(trajetoria)
    apresentacoes = [
        Apresentacao(a.data_apresentacao, a.conceito)
        for a in trajetoria.apresentacoes_qualificacao.all()
    ]
    resultado = calcular_situacao_marco(
        nivel=nivel,
        data_limite=data_limite,
        apresentacoes=apresentacoes,
        data_referencia=data_referencia,
        concluido_marcado=trajetoria.isQualificado,
    )
    return replace(resultado, origem_data_limite=origem)
    