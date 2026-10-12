from django.contrib import messages
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from .decoradores import tela_do_modulo
from .telas import TELAS
from .servicos import calcular_painel_docentes, calcular_painel_processos

@tela_do_modulo
def inicio(request):
    """Página inicial do módulo, com a lista das telas disponíveis."""
    telas = [{"titulo": titulo, "endereco": reverse(rota)} for titulo, rota in TELAS]
    return render(request, "acompanhamento/inicio.html", {"telas": telas})

@tela_do_modulo
def painel_docentes(request):
    """Exibe o painel de distribuição de docentes do PPGEC."""
    somente_permanentes = request.GET.get("somente_permanentes") in ["1", "true", "True"]
    contexto = calcular_painel_docentes(somente_permanentes=somente_permanentes)
    contexto["somente_permanentes"] = somente_permanentes
    return render(request, "acompanhamento/painel_docentes.html", contexto)


def _semestres_recentes(quantidade=6):
    """Semestre atual e os anteriores, do mais recente para o mais antigo."""
    hoje = timezone.localdate()
    ano, periodo = hoje.year, 1 if hoje.month <= 6 else 2
    semestres = []
    for _ in range(quantidade):
        semestres.append(f"{ano}.{periodo}")
        ano, periodo = (ano, 1) if periodo == 2 else (ano - 1, 2)
    return semestres


def _barras(contagens):
    """Converte {rótulo: total} em linhas com a largura relativa ao maior total."""
    maior = max(contagens.values(), default=0)
    return [
        {
            "rotulo": rotulo,
            "total": total,
            "largura": round(total * 100 / maior, 1) if maior else 0,
        }
        for rotulo, total in contagens.items()
    ]


@tela_do_modulo
def painel_processos(request):
    """Exibe os indicadores dos processos abertos no semestre escolhido."""
    semestre = request.GET.get("semestre") or None
    try:
        contexto = calcular_painel_processos(semestre=semestre)
    except ValueError:
        messages.error(request, "Semestre inválido. Use o formato AAAA.1 ou AAAA.2.")
        contexto = calcular_painel_processos()

    meses = {
        f"{chave[5:]}/{chave[:4]}": total
        for chave, total in contexto["abertos_por_mes"].items()
    }
    semestres = _semestres_recentes()
    if contexto["semestre"] not in semestres:
        semestres.append(contexto["semestre"])
    contexto.update(
        {
            "semestres": semestres,
            "barras_tipo": _barras(contexto["por_tipo"]),
            "barras_status": _barras(contexto["por_status"]),
            "barras_mes": _barras(meses),
        }
    )
    return render(request, "acompanhamento/painel_processos.html", contexto)
