from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .decoradores import tela_do_modulo
from .forms import MarcoCalendarioForm
from .models import MarcoCalendario
from .servicos import (
    calcular_painel_docentes,
    calcular_painel_processos,
    calcular_painel_sucesso_turma,
)
from .telas import TELAS


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


@tela_do_modulo
def calendario_marcos(request):
    """Lista os marcos do calendário e permite cadastrar/editar."""
    marcos = MarcoCalendario.objects.all().order_by("data_limite")

    marco_id = request.GET.get("editar")
    marco_edicao = None
    if marco_id:
        marco_edicao = get_object_or_404(MarcoCalendario, pk=marco_id)

    if request.method == "POST":
        form = MarcoCalendarioForm(request.POST, instance=marco_edicao)
        if form.is_valid():
            marco = form.save(commit=False)
            marco.alterado_por = request.user
            marco.save()
            return redirect("acompanhamento:calendario_marcos")
    else:
        form = MarcoCalendarioForm(instance=marco_edicao)

    contexto = {
        "marcos": marcos,
        "form": form,
        "marco_edicao": marco_edicao,
    }
    return render(request, "acompanhamento/calendario_marcos.html", contexto)


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
    data_inicio = request.GET.get("data_inicio") or None
    data_fim = request.GET.get("data_fim") or None

    # Se apenas uma das duas datas foi preenchida (data incompleta)
    if (data_inicio and not data_fim) or (not data_inicio and data_fim):
        messages.error(request, "Informe as datas inicial e final.")
        data_inicio = None
        data_fim = None

    try:
        contexto = calcular_painel_processos(
            semestre=semestre,
            data_inicio=data_inicio,
            data_fim=data_fim,
        )
    except ValueError as e:
        # Repassa a mensagem exata levantada pelo serviço ou fallback para semestre inválido
        mensagem = str(e) if str(e) else "Semestre inválido. Use o formato AAAA.1 ou AAAA.2."
        messages.error(request, mensagem)
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


@tela_do_modulo
def painel_sucesso_turma(request):
    """Exibe os indicadores do painel de sucesso por turma."""
    nivel_selecionado = request.GET.get("nivel", "TODOS")
    if nivel_selecionado not in ["TODOS", "MESTRADO", "DOUTORADO"]:
        nivel_selecionado = "TODOS"

    turmas = calcular_painel_sucesso_turma(nivel=nivel_selecionado)

    contexto = {
        "nivel_selecionado": nivel_selecionado,
        "turmas": turmas,
    }
    return render(request, "acompanhamento/painel_sucesso_turma.html", contexto)
