from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse

from .decoradores import tela_do_modulo
from .telas import TELAS
from .servicos import calcular_painel_docentes
from .models import MarcoCalendario
from .forms import MarcoCalendarioForm

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
