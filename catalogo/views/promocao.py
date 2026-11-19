import re
import unicodedata

from django.db.models import Case, Count, DateField, F, IntegerField, Q, Value, When
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from catalogo.models import Promocao
from catalogo.serializers import PromocaoSerializer
from core.permissions import IsAdminOrReadOnly


_ACENTOS = {
    'a': 'aáàâãä', 'e': 'eéèêë', 'i': 'iíìîï',
    'o': 'oóòôõö', 'u': 'uúùûü', 'c': 'cç',
    'n': 'nñ',
}


def _busca_nome_sem_acentos(texto):
    """Regex literal, portátil entre PostgreSQL e SQLite (sem extensão unaccent)."""
    sem_acentos = ''.join(
        letra for letra in unicodedata.normalize('NFD', texto)
        if not unicodedata.combining(letra)
    )
    return ''.join(
        f"[{_ACENTOS[letra.lower()]}]" if letra.lower() in _ACENTOS
        else re.escape(letra)
        for letra in sem_acentos
    )


class PromocaoViewSet(ModelViewSet):
    """RF03 — Cadastro de promoção (RN05 — somente administração cadastra)."""

    queryset = Promocao.objects.all().order_by('-data_inicio')
    serializer_class = PromocaoSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ['produto']

    @extend_schema(summary='Listagem administrativa paginada de promoções')
    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def admin_listagem(self, request):
        """Filtra e ordena no banco antes da paginação; mantém o editor existente."""
        busca = (request.query_params.get('busca') or '').strip()
        situacao = (request.query_params.get('situacao') or '').strip()
        if len(busca) > 100:
            raise ValidationError({'busca': 'Use no máximo 100 caracteres.'})
        if situacao not in ('', 'ativa', 'agendada', 'encerrada'):
            raise ValidationError({'situacao': 'Situação inválida.'})

        hoje = timezone.localdate()
        promocoes = Promocao.objects.select_related('produto')
        if busca:
            promocoes = promocoes.filter(produto__nome__iregex=_busca_nome_sem_acentos(busca))
        if situacao == 'ativa':
            promocoes = promocoes.filter(data_inicio__lte=hoje, data_fim__gte=hoje)
        elif situacao == 'agendada':
            promocoes = promocoes.filter(data_inicio__gt=hoje)
        elif situacao == 'encerrada':
            promocoes = promocoes.filter(data_fim__lt=hoje)

        # Igual ao agrupamento editorial anterior: ativas, agendadas,
        # encerradas. Desempate por ID garante paginação determinística.
        promocoes = promocoes.annotate(
            prioridade=Case(
                When(data_fim__lt=hoje, then=Value(2)),
                When(data_inicio__gt=hoje, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            ),
            vencimento_ativo=Case(
                When(data_inicio__lte=hoje, data_fim__gte=hoje, then=F('data_fim')),
                output_field=DateField(),
            ),
            inicio_agendado=Case(
                When(data_inicio__gt=hoje, then=F('data_inicio')),
                output_field=DateField(),
            ),
            fim_encerrado=Case(
                When(data_fim__lt=hoje, then=F('data_fim')),
                output_field=DateField(),
            ),
        ).order_by('prioridade', 'vencimento_ativo', 'inicio_agendado', '-fim_encerrado', 'pk')

        pagina = self.paginate_queryset(promocoes)
        if pagina is not None:
            return self.get_paginated_response(
                self.get_serializer(pagina, many=True).data
            )
        return Response(self.get_serializer(promocoes, many=True).data)

    @extend_schema(summary='Resumo administrativo agregado de promoções')
    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def resumo_admin(self, request):
        """Contagens globais, sem baixar todas as ofertas para o Dashboard."""
        hoje = timezone.localdate()
        return Response(Promocao.objects.aggregate(
            total=Count('pk'),
            ativas=Count('pk', filter=Q(data_inicio__lte=hoje, data_fim__gte=hoje)),
            agendadas=Count('pk', filter=Q(data_inicio__gt=hoje)),
            encerradas=Count('pk', filter=Q(data_fim__lt=hoje)),
        ))
