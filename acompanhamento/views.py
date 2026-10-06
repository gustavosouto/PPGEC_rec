from django.shortcuts import render
from django.urls import reverse

from .decoradores import tela_do_modulo
from .telas import TELAS
from .servicos import calcular_painel_docentes

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
