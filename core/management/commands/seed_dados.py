"""
Popula o banco com categorias, produtos, promoções, usuários e pedidos de
exemplo — útil para testar o frontend sem precisar cadastrar tudo na mão.

Uso:
    pdm run python manage.py seed_dados
    pdm run python manage.py seed_dados --limpar   (apaga os dados de exemplo antes de recriar)
"""

from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Categoria, ItemPedido, Pedido, Produto, Promocao, User

SENHA_PADRAO = 'senha123'


class Command(BaseCommand):
    help = 'Popula o banco de dados com categorias, produtos, promoções, usuários e pedidos de exemplo.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limpar',
            action='store_true',
            help='Remove os dados de exemplo criados por este comando antes de recriar.',
        )

    def handle(self, *args, **options):
        if options['limpar']:
            self._limpar()

        with transaction.atomic():
            categorias = self._criar_categorias()
            produtos = self._criar_produtos(categorias)
            self._criar_promocoes(produtos)
            admin, alunos = self._criar_usuarios()
            self._criar_pedidos(alunos, produtos)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Banco de dados populado com sucesso!'))
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('Credenciais de acesso (senha igual para todos):'))
        self.stdout.write(f'  Admin:  admin@cantina.ifc.edu.br / {SENHA_PADRAO}')
        self.stdout.write(f'  Aluno:  joao@aluno.ifc.edu.br / {SENHA_PADRAO}')
        self.stdout.write(f'  Aluno:  maria@aluno.ifc.edu.br / {SENHA_PADRAO}')
        self.stdout.write(f'  Aluno:  pedro@aluno.ifc.edu.br / {SENHA_PADRAO}')

    def _limpar(self):
        self.stdout.write('Removendo dados de exemplo existentes...')
        Pedido.objects.all().delete()
        Promocao.objects.all().delete()
        Produto.objects.all().delete()
        Categoria.objects.all().delete()
        User.objects.filter(email__endswith='@aluno.ifc.edu.br').delete()
        User.objects.filter(email='admin@cantina.ifc.edu.br').delete()

    def _criar_categorias(self):
        dados = [('Salgados', 1), ('Doces', 2), ('Bebidas', 3), ('Combos', 4)]
        categorias = {}
        for nome, ordem in dados:
            categoria, criada = Categoria.objects.get_or_create(nome=nome, defaults={'ordem': ordem})
            categorias[nome] = categoria
            self._log(nome, criada, 'categoria')
        return categorias

    def _criar_produtos(self, categorias):
        # nome, categoria, preco, preco_custo, estoque, unidade, destaque
        dados = [
            ('Coxinha de frango', 'Salgados', 8.00, 3.50, 25, 'unidade', True),
            ('Pastel de carne', 'Salgados', 7.50, 3.00, 20, 'unidade', False),
            ('Esfirra de queijo', 'Salgados', 6.50, 2.80, 18, 'unidade', False),
            ('Pão de queijo (4un)', 'Salgados', 9.00, 4.00, 15, 'unidade', False),
            ('Brigadeiro', 'Doces', 3.50, 1.20, 40, 'unidade', True),
            ('Brownie de chocolate', 'Doces', 6.00, 2.50, 22, 'unidade', False),
            ('Cookie recheado', 'Doces', 5.00, 2.00, 30, 'unidade', False),
            ('Bolo de cenoura (fatia)', 'Doces', 6.50, 2.80, 12, 'unidade', False),
            ('Suco de laranja', 'Bebidas', 6.00, 2.20, 30, 'ml', False),
            ('Suco de uva', 'Bebidas', 6.00, 2.20, 25, 'ml', False),
            ('Água mineral', 'Bebidas', 3.00, 1.00, 50, 'ml', False),
            ('Refrigerante lata', 'Bebidas', 5.50, 2.50, 35, 'unidade', False),
            ('Combo lanche + suco', 'Combos', 12.00, 5.50, 10, 'unidade', True),
        ]
        produtos = {}
        for nome, categoria_nome, preco, preco_custo, estoque, unidade, destaque in dados:
            produto, criado = Produto.objects.get_or_create(
                nome=nome,
                defaults={
                    'categoria': categorias[categoria_nome],
                    'preco': preco,
                    'preco_custo': preco_custo,
                    'estoque': estoque,
                    'estoque_minimo': 5,
                    'unidade_medida': unidade,
                    'destaque': destaque,
                    'descricao': f'{nome}, fresquinho, feito na cantina.',
                },
            )
            produtos[nome] = produto
            self._log(nome, criado, 'produto')
        return produtos

    def _criar_promocoes(self, produtos):
        hoje = date.today()
        # nome do produto, preço promocional, dias de início (relativo a hoje), dias de fim
        dados = [
            ('Coxinha de frango', 6.50, -1, 3),
            ('Brigadeiro', 2.50, -2, 5),
        ]
        for nome, preco_promocional, dias_inicio, dias_fim in dados:
            produto = produtos[nome]
            _, criada = Promocao.objects.get_or_create(
                produto=produto,
                data_inicio=hoje + timedelta(days=dias_inicio),
                data_fim=hoje + timedelta(days=dias_fim),
                defaults={'preco_promocional': preco_promocional},
            )
            self._log(f'promoção em {nome}', criada, 'promoção')

    def _criar_usuarios(self):
        admin, criado = User.objects.get_or_create(
            email='admin@cantina.ifc.edu.br',
            defaults={'name': 'Administração da Cantina', 'is_staff': True, 'is_superuser': True},
        )
        if criado:
            admin.set_password(SENHA_PADRAO)
            admin.save()
        self._log(admin.email, criado, 'usuário admin')

        dados_alunos = [
            ('João Silva', 'joao@aluno.ifc.edu.br'),
            ('Maria Souza', 'maria@aluno.ifc.edu.br'),
            ('Pedro Santos', 'pedro@aluno.ifc.edu.br'),
        ]
        alunos = []
        for nome, email in dados_alunos:
            aluno, criado = User.objects.get_or_create(email=email, defaults={'name': nome})
            if criado:
                aluno.set_password(SENHA_PADRAO)
                aluno.save()
            alunos.append(aluno)
            self._log(email, criado, 'usuário aluno')
        return admin, alunos

    def _criar_pedidos(self, alunos, produtos):
        if Pedido.objects.exists():
            self.stdout.write('  já existem pedidos no banco, pulando criação de pedidos de exemplo.')
            return

        # aluno, itens [(produto, quantidade), ...], status final desejado
        exemplos = [
            (alunos[0], [('Coxinha de frango', 2), ('Suco de laranja', 1)], Pedido.Status.RETIRADO),
            (alunos[1], [('Brigadeiro', 3), ('Água mineral', 1)], Pedido.Status.PRONTO),
            (alunos[2], [('Pastel de carne', 1)], Pedido.Status.CONFIRMADO),
            (alunos[0], [('Combo lanche + suco', 1)], Pedido.Status.PENDENTE),
        ]
        for aluno, itens, status_final in exemplos:
            pedido = Pedido.objects.create(usuario=aluno, status=status_final)
            for nome_produto, quantidade in itens:
                produto = produtos[nome_produto]
                ItemPedido.objects.create(
                    pedido=pedido,
                    produto=produto,
                    quantidade=quantidade,
                    preco_unitario=produto.preco_atual,
                )
                # Mantém coerência com a RN02 (baixa de estoque no momento do pedido)
                produto.estoque = max(produto.estoque - quantidade, 0)
                produto.save(update_fields=['estoque'])
            self.stdout.write(f'  + pedido #{pedido.id} criado para {aluno.email} ({status_final})')

    def _log(self, nome, criado, tipo):
        if criado:
            self.stdout.write(self.style.SUCCESS(f'  + {tipo} criado: {nome}'))
        else:
            self.stdout.write(f'  = {tipo} já existia: {nome}')
