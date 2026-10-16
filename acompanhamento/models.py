from django.core.exceptions import ValidationError
from django.db import models
from django.conf import settings

from processos.models import Aluno


class MarcoCalendario(models.Model):
    """Data da sessão de um marco acadêmico em um semestre.

    A data da sessão de projeto de dissertação e de qualificação muda a cada
    semestre. Este modelo só guarda o dado de entrada; a situação de cada
    aluno é calculada a partir dele e não é gravada aqui.
    """

    class TipoMarco(models.TextChoices):
        PROJETO_DISSERTACAO = "PROJETO_DISSERTACAO", "Projeto de dissertação"
        QUALIFICACAO = "QUALIFICACAO", "Qualificação"

    semestre = models.CharField(
        max_length=6,
        validators=[Aluno.semestre_validator],
        help_text="Semestre em que a sessão acontece, no formato YYYY.1 ou YYYY.2.",
    )
    tipo = models.CharField(max_length=20, choices=TipoMarco.choices)
    data_limite = models.DateField(
        verbose_name="Data limite",
        help_text="Data da sessão. Quem não apresentar até ela é tratado como reprovado.",
    )
    alterado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="+",
        verbose_name="Alterado por",
)
    alterado_em = models.DateTimeField(auto_now=True, verbose_name="Alterado em")

    class Meta:
        verbose_name = "marco do calendário"
        verbose_name_plural = "calendário de marcos"
        ordering = ["-semestre", "tipo"]
        constraints = [
            models.UniqueConstraint(
                fields=["semestre", "tipo"],
                name="marco_calendario_semestre_tipo_unico",
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} {self.semestre}: {self.data_limite:%d/%m/%Y}"

    @staticmethod
    def semestre_da_data(data) -> str:
        """Semestre letivo de uma data: janeiro a junho é .1, o resto é .2."""
        return f"{data.year}.{'1' if data.month <= 6 else '2'}"

    @classmethod
    def data_limite_do(cls, semestre: str, tipo: str):
        """Data cadastrada para o marco no semestre, ou None se não houver.

        O None significa "sem prazo cadastrado": quem consulta não deve tratar
        a ausência como prazo em aberto nem como prazo vencido.
        """
        return (
            cls.objects.filter(semestre=semestre, tipo=tipo)
            .values_list("data_limite", flat=True)
            .first()
        )

    def clean(self):
        super().clean()
        if self.semestre and self.data_limite:
            if self.semestre_da_data(self.data_limite) != self.semestre:
                raise ValidationError(
                    {"data_limite": "A data limite deve estar dentro do semestre informado."}
                )