from celery import shared_task


@shared_task(name="acompanhamento.tasks.enviar_avisos_irregularidade")
def enviar_avisos_irregularidade():
    from acompanhamento.avisos import rodar_aviso_diario

    return rodar_aviso_diario()