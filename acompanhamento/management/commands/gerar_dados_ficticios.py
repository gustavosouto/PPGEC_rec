"""Comando que popula o banco com dados fictícios para desenvolvimento.

Usuários criados aqui têm e-mail @ficticio.invalid e polos começam com
"Fictício". A remoção usa essas marcas, então nada real é apagado.
"""

import random
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from processos.models import Aluno, Docente, Polo, Processo, Setor, User

DOMINIO = "@ficticio.invalid"
PREFIXO_POLO = "Fictício"
NOMES_POLOS = ["Fictício Recife", "Fictício Caruaru"]

PRENOMES = [
    "Ana", "Bruno", "Carla", "Diego", "Elisa", "Fábio", "Gabriela", "Heitor",
    "Isabela", "João", "Larissa", "Marcos", "Natália", "Otávio", "Paula",
    "Rafael", "Sofia", "Tiago", "Vitória", "Wagner",
]
SOBRENOMES = [
    "Almeida", "Barros", "Cavalcanti", "Duarte", "Esteves", "Ferraz",
    "Gusmão", "Holanda", "Lins", "Moura", "Nogueira", "Pessoa", "Queiroz",
    "Rêgo", "Siqueira", "Tavares",
]

STATUS_ABERTOS = [
    Processo.StatusProcesso.EM_ANALISE,
    Processo.StatusProcesso.AGUARDANDO_DOCUMENTO,
    Processo.StatusProcesso.AGUARDANDO_CIENCIA,
    Processo.StatusProcesso.EM_DEBATE,
]

# Quantos dias para trás os processos podem ter sido abertos (um pouco
# mais de seis meses, que é o mínimo pedido).
JANELA_DIAS = 200


class Command(BaseCommand):
    help = "Remove os dados fictícios anteriores e cria um conjunto novo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--semente", type=int, default=42,
            help="Mesma semente gera sempre os mesmos dados (padrão: 42).",
        )
        parser.add_argument(
            "--data-referencia", type=date.fromisoformat, default=None,
            help="Data usada como 'hoje', no formato AAAA-MM-DD (padrão: hoje).",
        )
        parser.add_argument(
            "--apenas-remover", action="store_true",
            help="Só remove os dados fictícios, sem criar novos.",
        )

    def handle(self, *args, **opcoes):
        # Só roda em desenvolvimento. Checado antes de mexer no banco.
        if not settings.DEBUG:
            raise CommandError(
                "Recusado: o modo de desenvolvimento está desligado (DEBUG=False)."
            )

        self.rng = random.Random(opcoes["semente"])
        self.referencia = opcoes["data_referencia"] or timezone.localdate()
        self.nomes_usados = set()

        # Se der erro no meio, desfaz tudo.
        with transaction.atomic():
            removidos = self.remover()
            if opcoes["apenas_remover"]:
                resumo = {}
            else:
                resumo = self.criar()

        self.imprimir_resumo(removidos, resumo)

    def remover(self):
        # Os processos vão primeiro porque o Processo tem PROTECT no usuário.
        processos = Processo.objects.filter(
            Q(usuario_criado_por__email__endswith=DOMINIO)
            | Q(aluno_interessado__email__endswith=DOMINIO)
        )
        total_processos = processos.count()
        processos.delete()

        usuarios = User.objects.filter(email__endswith=DOMINIO)
        total_usuarios = usuarios.count()
        usuarios.delete()

        polos = Polo.objects.filter(nome__startswith=PREFIXO_POLO)
        total_polos = polos.count()
        polos.delete()

        return {
            "Processos": total_processos,
            "Usuários": total_usuarios,
            "Polos": total_polos,
        }

    def criar(self):
        resumo = {}

        for nome in NOMES_POLOS:
            Polo.objects.create(nome=nome, descricao="Polo de dados fictícios")
        resumo["Polos fictícios"] = len(NOMES_POLOS)

        resumo.update(self.criar_docentes())

        alunos = self.criar_alunos(quantidade=8)
        resumo["Alunos"] = len(alunos)

        resumo.update(self.criar_processos(alunos))
        return resumo

    def criar_docentes(self):
        # Um docente para cada combinação (permanente/colaborador e
        # interno/externo) em cada polo ativo. O None é o grupo sem polo.
        contagem = {}
        polos = list(Polo.objects.filter(ativo=True)) + [None]

        for polo in polos:
            for permanente in (True, False):
                for externo in (False, True):
                    docente = Docente(
                        nome=self.nome_aleatorio(),
                        permanente=permanente,
                        externo=externo,
                        polo_atuacao=polo,
                    )
                    docente.email = self.email_para(docente.nome)
                    docente.set_unusable_password()
                    docente.save()

                    categoria = "permanentes" if permanente else "colaboradores"
                    vinculo = "externos" if externo else "internos"
                    chave = f"Docentes {categoria} {vinculo}"
                    contagem[chave] = contagem.get(chave, 0) + 1

        contagem["Docentes sem polo (já incluídos acima)"] = 4
        return contagem

    def criar_alunos(self, quantidade):
        alunos = []
        for _ in range(quantidade):
            aluno = Aluno(nome=self.nome_aleatorio())
            aluno.email = self.email_para(aluno.nome)
            aluno.set_unusable_password()
            aluno.save()
            alunos.append(aluno)
        return alunos

    def criar_processos(self, alunos):
        # Um processo aberto e um finalizado de cada tipo.
        setor = Setor.objects.filter(nome=Setor.NOME_SECRETARIA).first()
        if setor is None:
            raise CommandError(
                f"Setor '{Setor.NOME_SECRETARIA}' não encontrado. Rode o migrate antes."
            )

        pedidos = []
        for tipo in Processo.TipoProcesso:
            pedidos.append((tipo, False))
            pedidos.append((tipo, True))

        # Datas igualmente espaçadas na janela (assim cobre os seis meses
        # com certeza) e depois embaralhadas.
        dias_atras = [
            round(i * JANELA_DIAS / (len(pedidos) - 1)) for i in range(len(pedidos))
        ]
        self.rng.shuffle(dias_atras)

        abertos = 0
        finalizados = 0
        for (tipo, finalizado), dias in zip(pedidos, dias_atras):
            aluno = self.rng.choice(alunos)
            criado_em = self.referencia - timedelta(days=dias)
            prazo = criado_em + timedelta(days=Processo.prazo_dias_para_tipo(tipo))

            processo = Processo(
                usuario_criado_por=aluno,
                aluno_interessado=aluno,
                tipo=tipo,
                assunto=f"{tipo.label} (fictício)",
                descricao="Processo gerado pelo comando de dados fictícios.",
                setor_atual=setor,
                prazo_limite=prazo,
            )
            if finalizado:
                processo.status = Processo.StatusProcesso.FINALIZADO
                fim = min(prazo, self.referencia)
                processo.finalizado_em = self.para_datetime(fim)
                processo.termo_finalizacao = "Finalizado nos dados fictícios."
                finalizados += 1
            else:
                processo.status = self.rng.choice(STATUS_ABERTOS)
                abertos += 1
            processo.save()

            # data_criacao é auto_now_add, então o save ignora a data que a
            # gente quer. O update() grava direto no banco.
            Processo.objects.filter(pk=processo.pk).update(
                data_criacao=self.para_datetime(criado_em)
            )

        return {"Processos abertos": abertos, "Processos finalizados": finalizados}

    def nome_aleatorio(self):
        # Sorteia até achar um nome que ainda não saiu nesta execução.
        while True:
            nome = (
                f"{self.rng.choice(PRENOMES)} "
                f"{self.rng.choice(SOBRENOMES)} {self.rng.choice(SOBRENOMES)}"
            )
            if nome not in self.nomes_usados:
                self.nomes_usados.add(nome)
                return nome

    def email_para(self, nome):
        # "Fábio Lins Rêgo" -> fabio.lins.rego@ficticio.invalid
        sem_acento = nome.lower().translate(str.maketrans("áâãéêíóôõúç", "aaaeeiooouc"))
        return sem_acento.replace(" ", ".") + DOMINIO

    def para_datetime(self, dia):
        return timezone.make_aware(datetime.combine(dia, time(9, 0)))

    def imprimir_resumo(self, removidos, resumo):
        self.stdout.write("Removidos:")
        for categoria, total in removidos.items():
            self.stdout.write(f"  {categoria}: {total}")

        if resumo:
            self.stdout.write(self.style.SUCCESS("Criados:"))
            for categoria, total in resumo.items():
                self.stdout.write(f"  {categoria}: {total}")