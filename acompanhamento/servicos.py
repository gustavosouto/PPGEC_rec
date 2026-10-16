from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Count, Q
from processos.models import Docente, Polo


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
