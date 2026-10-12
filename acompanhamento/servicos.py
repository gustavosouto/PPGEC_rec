from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Avg, Count, F, Q
from django.utils import timezone
from processos.models import Docente, Polo, Processo


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
        "total_internos": total_internos,
        "total_externos": total_externos,
        "total_distribuicao": total_distribuicao,
        "distribuicao_polos": linhas_distribuicao,
        "somente_permanentes": somente_permanentes,
    }

def calcular_painel_processos(semestre=None):
    """
    Calcula indicadores do painel de processos/solicitações dos discentes.

    Métricas calculadas:
    - Quantidade por tipo de processo e por status;
    - Volume mensal (processos abertos por mês, incluindo meses sem processos com 0);
    - Tempo médio de resolução em dias (None caso não haja finalizados);
    - Quantidade de processos em atraso (usando esta_atrasado).
    """
    # 1. Definição do semestre padrão ou validação do parâmetro
    hoje = timezone.localdate()
    if semestre is None:
        semestre = f"{hoje.year}.{'1' if hoje.month <= 6 else '2'}"

    # Validação do formato do semestre (YYYY.1 ou YYYY.2)
    partes = str(semestre).split(".")
    if len(partes) != 2 or partes[1] not in {"1", "2"} or not partes[0].isdigit() or len(partes[0]) != 4:
        raise ValueError(f"Semestre inválido: '{semestre}'. Utilize o formato YYYY.1 ou YYYY.2.")

    ano = int(partes[0])
    periodo = partes[1]

    if periodo == "1":
        meses_semestre = [f"{ano}-{m:02d}" for m in range(1, 7)]
        inicio = timezone.datetime(ano, 1, 1, tzinfo=timezone.get_current_timezone())
        fim = timezone.datetime(ano, 6, 30, 23, 59, 59, tzinfo=timezone.get_current_timezone())
    else:
        meses_semestre = [f"{ano}-{m:02d}" for m in range(7, 13)]
        inicio = timezone.datetime(ano, 7, 1, tzinfo=timezone.get_current_timezone())
        fim = timezone.datetime(ano, 12, 31, 23, 59, 59, tzinfo=timezone.get_current_timezone())

    queryset = Processo.objects.filter(data_criacao__range=(inicio, fim))

    total_processos = queryset.count()

    # Contagem por tipo de processo
    contagem_por_tipo = {}
    for item in queryset.values("tipo").annotate(total=Count("id")).order_by("-total"):
        tipo_valor = item["tipo"]
        label = dict(Processo.TipoProcesso.choices).get(tipo_valor, tipo_valor)
        contagem_por_tipo[label] = item["total"]

    # Contagem por status
    contagem_por_status = {}
    for item in queryset.values("status").annotate(total=Count("id")).order_by("-total"):
        status_valor = item["status"]
        label = dict(Processo.StatusProcesso.choices).get(status_valor, status_valor)
        contagem_por_status[label] = item["total"]

    # 2. Processos abertos por mês com zeros pré-populados para todos os meses do período
    abertos_por_mes = {mes: 0 for mes in meses_semestre}
    for proc in queryset.order_by("data_criacao"):
        chave_mes = proc.data_criacao.strftime("%Y-%m")
        if chave_mes in abertos_por_mes:
            abertos_por_mes[chave_mes] += 1

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
        "total_processos": total_processos,
        "por_tipo": contagem_por_tipo,
        "por_status": contagem_por_status,
        "abertos_por_mes": abertos_por_mes,
        "tempo_medio_dias": tempo_medio_dias,
        "total_atrasados": total_atrasados,
    }
