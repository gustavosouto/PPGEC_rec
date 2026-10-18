"""Aviso diário de alunos que ficaram atrasados.

Calcula a situação de todos os alunos ativos, guarda um aviso para quem
ficou atrasado e manda um e-mail só com os avisos novos para a Secretaria
PPGEC e a Coordenação PPG. Sem aviso novo, nenhum e-mail sai.
"""

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from acompanhamento.lista_alunos import _trajetorias_ativas
from acompanhamento.models import AvisoIrregularidade
from acompanhamento.situacao import (
    IRREGULAR_COM_CHANCE,
    IRREGULAR_SEM_CHANCE,
    calcular_situacoes,
)
from processos.models import Aluno, Setor, User

ATRASADO = (IRREGULAR_COM_CHANCE, IRREGULAR_SEM_CHANCE)
MARCOS = (AvisoIrregularidade.Marco.PROJETO_QUALIFICACAO, AvisoIrregularidade.Marco.DEFESA)
SETORES_AVISADOS = (Setor.NOME_SECRETARIA, Setor.NOME_COORDENACAO)


def rodar_aviso_diario(data_referencia=None):
    """Atualiza os avisos e manda o e-mail do dia."""
    novos = atualizar_avisos(data_referencia)
    enviados = enviar_email(novos)
    return {"avisos_novos": len(novos), "emails_enviados": enviados}


@transaction.atomic
def atualizar_avisos(data_referencia=None):
    """Cria os avisos de quem ficou atrasado e encerra os de quem saiu.

    Devolve os avisos criados agora.
    """
    if data_referencia is None:
        data_referencia = timezone.localdate()
    agora = timezone.now()

    trajetorias = _trajetorias_ativas(Aluno.objects.all())
    situacoes = calcular_situacoes(trajetorias, data_referencia)

    abertos = {}
    for aviso in AvisoIrregularidade.objects.filter(encerrado_em__isnull=True):
        abertos[(aviso.trajetoria_id, aviso.marco)] = aviso

    novos = []
    for trajetoria in trajetorias:
        for marco in MARCOS:
            situacao = situacoes[trajetoria.pk][marco].situacao
            aberto = abertos.pop((trajetoria.pk, marco), None)

            # Continua atrasado do mesmo jeito: o aviso já existe.
            if aberto and aberto.situacao == situacao:
                continue

            # Saiu do atraso ou mudou de situação: o aviso antigo acaba.
            if aberto:
                aberto.encerrado_em = agora
                aberto.save(update_fields=["encerrado_em"])

            if situacao in ATRASADO:
                aviso = AvisoIrregularidade.objects.create(
                    trajetoria=trajetoria, marco=marco, situacao=situacao
                )
                novos.append(aviso)

    # Sobram os avisos de quem deixou de estar ativo (trancou, foi desligado
    # ou concluiu). Eles também acabam.
    for aviso in abertos.values():
        aviso.encerrado_em = agora
        aviso.save(update_fields=["encerrado_em"])

    return novos


def destinatarios():
    """E-mails dos membros atuais da Secretaria PPGEC e da Coordenação PPG."""
    emails = (
        User.objects.filter(
            is_active=True,
            participacoes_setor__setor__nome__in=SETORES_AVISADOS,
            participacoes_setor__data_saida__isnull=True,
        )
        .exclude(email="")
        .values_list("email", flat=True)
        .distinct()
    )
    return sorted(emails)


def enviar_email(avisos):
    """Manda um e-mail com os avisos. Devolve 1 se enviou e 0 se não."""
    if not avisos:
        return 0
    emails = destinatarios()
    if not emails:
        return 0

    html = render_to_string(
        "acompanhamento/emails/aviso_irregularidade.html",
        {"avisos": avisos, "site_url": settings.SITE_URL},
    )
    send_mail(
        subject=f"[PPGEC] {len(avisos)} aluno(s) com prazo vencido",
        message="",
        from_email=None,
        recipient_list=emails,
        html_message=html,
        fail_silently=False,
    )

    agora = timezone.now()
    for aviso in avisos:
        aviso.enviado_em = agora
        aviso.save(update_fields=["enviado_em"])
    return 1