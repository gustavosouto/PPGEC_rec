from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Avg, Count, F, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone

from processos.models import Docente, Polo, Processo


def validar_semestre(semestre):
    """Valida o formato AAAA.1/AAAA.2 e retorna (ano, período)."""
    partes = str(semestre).split(".")
    if (
        len(partes) != 2
        or partes[1] not in {"1", "2"}
        or not partes[0].isdigit()
        or len(partes[0]) != 4
        or not 1 <= int(partes[0]) <= 9999
    ):
        raise ValueError(f"Semestre inválido: '{semestre}'. Utilize o formato YYYY.1 ou YYYY.2.")
    return int(partes[0]), partes[1]


def calcular_painel_docentes(somente_permanentes=False):
    """
    Calcula indicadores de distribuição de docentes ativos do programa.
    
    Permite filtrar opcionalmente por somente_permanentes.
    Agrupa externos sob a categoria 'Externo à UPE' e docentes sem polo
    válido ou associados ao Polo Sede / polos inativos como 'Polo não informado'.
    Garante percentuais exatos cuja soma totaliza 100%.
    """
    docentes_ativos = Docente.objects.filter(is_active=True)

    # Contagens gerais dos docentes ativos (independente de polo)
    total_ativos = docentes_ativos.count()
    total_permanentes = docentes_ativos.filter(permanente=True).count()
    total_colaboradores = docentes_ativos.filter(permanente=False).count()
    total_externos = docentes_ativos.filter(externo=True).count()
    total_internos = docentes_ativos.filter(externo=False).count()

    if total_ativos > 0:
        percentual_permanentes = (
            Decimal(total_permanentes) * Decimal("100.0") / Decimal(total_ativos)
        ).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        percentual_colaboradores = Decimal("100.0") - percentual_permanentes
    else:
        percentual_permanentes = Decimal("0.0")
        percentual_colaboradores = Decimal("0.0")

    # Base para a distribuição (aplicando o filtro opcional se solicitado)
    base_distribuicao = docentes_ativos
    if somente_permanentes:
        base_distribuicao = base_distribuicao.filter(permanente=True)

    total_distribuicao = base_distribuicao.count()

    # 1. Externos à UPE (formam linha própria independente do polo)
    qtd_externos = base_distribuicao.filter(externo=True).count()

    # 2. Polos ativos válidos (excluindo qualquer polo genérico nomeado 'Polo Sede')
    polos_validos = (
        Polo.objects.filter(ativo=True)
        .exclude(nome__iexact="Polo Sede")
        .order_by("nome")
    )

    linhas_distribuicao = []
    qtd_em_polos_validos = 0

    for polo in polos_validos:
        # Apenas docentes internos contam nos polos individuais
        qtd = base_distribuicao.filter(
            externo=False,
            polo_atuacao=polo,
        ).count()
        if qtd > 0:
            linhas_distribuicao.append({
                "id": polo.id,
                "nome": polo.nome,
                "total_docentes": qtd,
            })
            qtd_em_polos_validos += qtd

    # 3. Polo não informado: internos que não entraram nos polos válidos
    # (sem polo, ligados ao Polo Sede ou associados a polos inativos)
    qtd_polo_nao_informado = total_distribuicao - qtd_externos - qtd_em_polos_validos

    if qtd_polo_nao_informado > 0 or total_distribuicao == 0:
        linhas_distribuicao.append({
            "id": None,
            "nome": "Polo não informado",
            "total_docentes": qtd_polo_nao_informado,
        })

    if qtd_externos > 0:
        linhas_distribuicao.append({
            "id": None,
            "nome": "Externo à UPE",
            "total_docentes": qtd_externos,
        })

    # Cálculo dos percentuais com ajuste de arredondamento (soma exata de 100%)
    if total_distribuicao > 0:
        soma_percentual = Decimal("0.0")
        for item in linhas_distribuicao:
            percentual = (
                Decimal(item["total_docentes"]) * Decimal("100.0") / Decimal(total_distribuicao)
            ).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
            item["percentual"] = float(percentual)
            soma_percentual += percentual

        # Ajuste no último item com quantidade maior que zero caso haja resíduo de arredondamento
        diferenca = Decimal("100.0") - soma_percentual
        if diferenca != Decimal("0.0"):
            for item in reversed(linhas_distribuicao):
                if item["total_docentes"] > 0:
                    item["percentual"] = round(item["percentual"] + float(diferenca), 1)
                    break
    else:
        for item in linhas_distribuicao:
            item["percentual"] = 0.0

    return {
        "total_ativos": total_ativos,
        "total_permanentes": total_permanentes,
        "total_colaboradores": total_colaboradores,
        "percentual_permanentes": percentual_permanentes,
        "percentual_colaboradores": percentual_colaboradores,
        "total_internos": total_internos,
        "total_externos": total_externos,
        "total_distribuicao": total_distribuicao,
        "distribuicao_polos": linhas_distribuicao,
        "somente_permanentes": somente_permanentes,
    }

def calcular_painel_processos(semestre=None, data_inicio=None, data_fim=None):
    """
    Calcula indicadores do painel de processos/solicitações dos discentes.

    Métricas calculadas:
    - Quantidade por tipo de processo e por status;
    - Volume mensal e quantidade por tipo em cada mês do período;
    - Tempo médio de resolução em dias (None caso não haja finalizados);
    - Quantidade de processos em atraso (usando esta_atrasado).

    Um intervalo completo de datas prevalece sobre o semestre informado.
    Sem datas, usa o semestre informado ou o semestre atual.
    """
    hoje = timezone.localdate()
    intervalo_personalizado = data_inicio is not None or data_fim is not None

    if intervalo_personalizado:
        if data_inicio is None or data_fim is None:
            raise ValueError("Informe as datas inicial e final.")
        if data_inicio > data_fim:
            raise ValueError("A data inicial deve ser anterior ou igual à data final.")
    else:
        if semestre is None:
            semestre = f"{hoje.year}.{'1' if hoje.month <= 6 else '2'}"

        ano, periodo = validar_semestre(semestre)
        if periodo == "1":
            data_inicio = date(ano, 1, 1)
            data_fim = date(ano, 6, 30)
        else:
            data_inicio = date(ano, 7, 1)
            data_fim = date(ano, 12, 31)

    queryset = Processo.objects.filter(data_criacao__date__range=(data_inicio, data_fim))

    total_processos = queryset.count()

    # Agrupa em uma consulta só por tipo e mês para os dois gráficos.
    contagens_tipo_mes = queryset.annotate(
        mes=TruncMonth("data_criacao", tzinfo=timezone.get_current_timezone())
    ).values("tipo", "mes").annotate(total=Count("id")).order_by("mes", "tipo")

    contagem_por_tipo = {}
    abertos_por_mes = {}
    ano_mes = (data_inicio.year, data_inicio.month)
    ultimo_ano_mes = (data_fim.year, data_fim.month)
    while ano_mes <= ultimo_ano_mes:
        ano, mes = ano_mes
        abertos_por_mes[f"{ano}-{mes:02d}"] = 0
        ano_mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)

    por_tipo_por_mes = []
    rotulos_tipos = dict(Processo.TipoProcesso.choices)
    for item in contagens_tipo_mes:
        tipo_valor = item["tipo"]
        rotulo_tipo = rotulos_tipos.get(tipo_valor, tipo_valor)
        chave_mes = item["mes"].strftime("%Y-%m")
        contagem_por_tipo[rotulo_tipo] = (
            contagem_por_tipo.get(rotulo_tipo, 0) + item["total"]
        )
        abertos_por_mes[chave_mes] += item["total"]
        por_tipo_por_mes.append(
            {
                "mes": chave_mes,
                "tipo": rotulo_tipo,
                "total": item["total"],
            }
        )
    contagem_por_tipo = dict(
        sorted(contagem_por_tipo.items(), key=lambda item: item[1], reverse=True)
    )

    # Contagem por status
    contagem_por_status = {}
    for item in queryset.values("status").annotate(total=Count("id")).order_by("-total"):
        status_valor = item["status"]
        label = dict(Processo.StatusProcesso.choices).get(status_valor, status_valor)
        contagem_por_status[label] = item["total"]

    # 3. Tempo médio de resolução (None caso não haja finalizados)
    finalizados = queryset.filter(
        Q(finalizado_em__isnull=False) | Q(status=Processo.StatusProcesso.FINALIZADO)
    )
    tempos_dias = []
    for proc in finalizados:
        data_fim = proc.finalizado_em or proc.atualizado_em
        if data_fim and proc.data_criacao:
            diferenca = (data_fim - proc.data_criacao).total_seconds() / 86400
            if diferenca >= 0:
                tempos_dias.append(diferenca)

    if tempos_dias:
        tempo_medio_dias = round(sum(tempos_dias) / len(tempos_dias), 1)
    else:
        tempo_medio_dias = None

    # 4. Quantidade de processos em atraso
    total_atrasados = sum(1 for proc in queryset if proc.esta_atrasado)

    return {
        "semestre": semestre,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "total_processos": total_processos,
        "por_tipo": contagem_por_tipo,
        "por_tipo_por_mes": por_tipo_por_mes,
        "por_status": contagem_por_status,
        "abertos_por_mes": abertos_por_mes,
        "tempo_medio_dias": tempo_medio_dias,
        "total_atrasados": total_atrasados,
    }
