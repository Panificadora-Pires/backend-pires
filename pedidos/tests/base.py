"""Setup compartilhado pelos testes do app pedidos."""

from django.contrib.auth import get_user_model

from catalogo.models import Categoria, Produto

User = get_user_model()


class CriaUsuariosEProdutosMixin:
    def criar_usuarios(self):
        self.admin = User.objects.create_user(email='admin@teste.com', password='senha12345', is_staff=True)
        self.aluno = User.objects.create_user(email='aluno@teste.com', password='senha12345')
        self.outro_aluno = User.objects.create_user(email='outro@teste.com', password='senha12345')

    def criar_produtos(self):
        self.categoria = Categoria.objects.create(nome='Salgados', ordem=1)
        self.coxinha = Produto.objects.create(
            nome='Coxinha de frango', categoria=self.categoria, preco=8.00, preco_custo=3.50, estoque=10
        )
        self.suco = Produto.objects.create(
            nome='Suco de laranja', categoria=self.categoria, preco=6.00, preco_custo=2.20, estoque=5
        )
