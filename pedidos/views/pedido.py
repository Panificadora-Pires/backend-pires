from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import F, Sum
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status as http_status
from rest_framework.decorators import action
from rest_framework.mixins import CreateModelMixin, ListModelMixin, RetrieveModelMixin
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from core.permissions import IsOwnerOrAdmin
from pedidos.models import ItemPedido, Pedido
from pedidos.serializers import (
    CheckoutDinheiroSerializer,
    CheckoutMercadoPagoSerializer,
    PagamentoPedidoSerializer,
    PedidoSerializer,
    PedidoStatusUpdateSerializer,
    RetiradaPorQRCodeSerializer,
)
from pedidos.services.pagamentos import (
    MercadoPagoError,
    aplicar_dados_order,
    consultar_order_mercado_pago,
    criar_order_mercado_pago,
    forma_pagamento_por_dados,
    prazo_pagamento,
    validar_assinatura_webhook,
)
from pedidos.services.pedido import criar_pedido_reservando_estoque
from pedidos.utils import gerar_qrcode_base64


class PedidoViewSet(
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    GenericViewSet,
):
    """Criação, consulta, pagamento e retirada de pedidos."""

    serializer_class = PedidoSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    filterset_fields = ['status']

    def get_queryset(self):
        usuario = self.request.user
        queryset = (
            Pedido.objects
            .select_related('usuario')
            .prefetch_related('itens__produto')
            .order_by('-data')
        )
        if usuario.is_staff:
            return queryset
        return queryset.filter(usuario=usuario)

    def _resposta_checkout(self, pedido, *, status_code=http_status.HTTP_200_OK):
        pedido.refresh_from_db()
        return Response(
            {
                'pedido': PedidoSerializer(pedido).data,
                'pagamento': PagamentoPedidoSerializer(pedido).data,
            },
            status=status_code,
        )

    @action(detail=False, methods=['post'])
    def checkout_dinheiro(self, request):
        serializer = CheckoutDinheiroSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        checkout_id = serializer.validated_data['checkout_id']

        existente = Pedido.objects.filter(
            usuario=request.user,
            checkout_id=checkout_id,
        ).first()
        if existente:
            return self._resposta_checkout(existente)

        try:
            pedido = criar_pedido_reservando_estoque(
                usuario=request.user,
                itens_data=serializer.validated_data['itens_criacao'],
                checkout_id=checkout_id,
                forma_pagamento=Pedido.FormaPagamento.DINHEIRO,
                status_pagamento=Pedido.StatusPagamento.PENDENTE,
            )
        except IntegrityError:
            pedido = Pedido.objects.get(
                usuario=request.user,
                checkout_id=checkout_id,
            )
            return self._resposta_checkout(pedido)

        return self._resposta_checkout(
            pedido,
            status_code=http_status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['post'])
    def checkout_mercado_pago(self, request):
        serializer = CheckoutMercadoPagoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dados = serializer.validated_data
        checkout_id = dados['checkout_id']
        pedido = Pedido.objects.filter(
            usuario=request.user,
            checkout_id=checkout_id,
        ).first()
        criado = False

        if pedido and pedido.status == Pedido.Status.CANCELADO:
            return Response(
                {
                    'detail': 'Este checkout foi encerrado. Inicie uma nova tentativa de pagamento.',
                    'novo_checkout': True,
                },
                status=http_status.HTTP_409_CONFLICT,
            )

        if not pedido:
            forma = forma_pagamento_por_dados(
                dados['payment_type'],
                dados['form_data'],
            )
            if not forma:
                return Response(
                    {'detail': 'Este checkout aceita somente Pix ou cartão.'},
                    status=http_status.HTTP_400_BAD_REQUEST,
                )

            try:
                pedido = criar_pedido_reservando_estoque(
                    usuario=request.user,
                    itens_data=dados['itens_criacao'],
                    checkout_id=checkout_id,
                    forma_pagamento=forma,
                    status_pagamento=Pedido.StatusPagamento.PROCESSANDO,
                    pagamento_expira_em=prazo_pagamento(),
                )
                criado = True
            except IntegrityError:
                pedido = Pedido.objects.get(
                    usuario=request.user,
                    checkout_id=checkout_id,
                )

        if pedido.mercadopago_order_id:
            try:
                remoto = consultar_order_mercado_pago(
                    pedido.mercadopago_order_id,
                )
                pedido = aplicar_dados_order(
                    pedido,
                    remoto,
                    payment_type=dados['payment_type'],
                )
            except MercadoPagoError:
                pass
            return self._resposta_checkout(pedido)

        try:
            remoto = criar_order_mercado_pago(
                pedido=pedido,
                payment_type=dados['payment_type'],
                form_data=dados['form_data'],
            )
            pedido = aplicar_dados_order(
                pedido,
                remoto,
                payment_type=dados['payment_type'],
            )
        except MercadoPagoError as exc:
            if exc.estado_incerto:
                return Response(
                    {
                        'detail': str(exc),
                        'pedido_id': pedido.id,
                        'reutilizar_checkout': True,
                    },
                    status=exc.status_code or http_status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            pedido.status_pagamento = Pedido.StatusPagamento.ERRO
            pedido.mercadopago_status_detail = str(exc)
            pedido.save(
                update_fields=['status_pagamento', 'mercadopago_status_detail']
            )

            # Erro definitivo de validação/API: encerra a reserva para o usuário
            # poder tentar novamente com um novo checkout.
            if pedido.status != Pedido.Status.CANCELADO:
                pedido.status = Pedido.Status.CANCELADO
                pedido.save(update_fields=['status'])
                from pedidos.services.pedido import devolver_estoque_pedido
                devolver_estoque_pedido(pedido)

            return Response(
                {
                    'detail': str(exc),
                    'novo_checkout': True,
                    'provider': exc.data,
                },
                status=(
                    exc.status_code
                    if exc.status_code and exc.status_code < 500
                    else http_status.HTTP_502_BAD_GATEWAY
                ),
            )

        return self._resposta_checkout(
            pedido,
            status_code=(
                http_status.HTTP_201_CREATED
                if criado
                else http_status.HTTP_200_OK
            ),
        )

    @action(detail=True, methods=['get'])
    def pagamento(self, request, pk=None):
        pedido = self.get_object()
        sincronizacao = 'local'

        if (
            pedido.forma_pagamento in {
                Pedido.FormaPagamento.PIX,
                Pedido.FormaPagamento.CARTAO,
            }
            and pedido.mercadopago_order_id
            and pedido.status_pagamento not in {
                Pedido.StatusPagamento.APROVADO,
                Pedido.StatusPagamento.RECUSADO,
                Pedido.StatusPagamento.CANCELADO,
                Pedido.StatusPagamento.REEMBOLSADO,
            }
        ):
            try:
                remoto = consultar_order_mercado_pago(
                    pedido.mercadopago_order_id,
                )
                pedido = aplicar_dados_order(pedido, remoto)
                sincronizacao = 'mercado_pago'
            except MercadoPagoError:
                sincronizacao = 'indisponivel'

        return Response(
            {
                'pedido': PedidoSerializer(pedido).data,
                'pagamento': PagamentoPedidoSerializer(pedido).data,
                'sincronizacao': sincronizacao,
            }
        )

    @action(
        detail=False,
        methods=['post'],
        permission_classes=[AllowAny],
        authentication_classes=[],
    )
    def mercado_pago_webhook(self, request):
        data_id_query = request.query_params.get('data.id')
        data_id_body = (request.data.get('data') or {}).get('id')
        data_id = data_id_query or data_id_body

        if not validar_assinatura_webhook(
            x_signature=request.headers.get('x-signature'),
            x_request_id=request.headers.get('x-request-id'),
            data_id=data_id_query,
        ):
            return Response(
                {'detail': 'Assinatura de webhook inválida.'},
                status=http_status.HTTP_401_UNAUTHORIZED,
            )

        if request.query_params.get('type') not in {None, 'order'}:
            return Response(status=http_status.HTTP_200_OK)
        if not data_id:
            return Response(status=http_status.HTTP_200_OK)

        try:
            remoto = consultar_order_mercado_pago(data_id)
        except MercadoPagoError:
            # 5xx faz o Mercado Pago tentar entregar novamente.
            return Response(status=http_status.HTTP_503_SERVICE_UNAVAILABLE)

        pedido = None
        order_id = remoto.get('id') or data_id
        external_reference = remoto.get('external_reference')

        if order_id:
            pedido = Pedido.objects.filter(
                mercadopago_order_id=str(order_id),
            ).first()
        if pedido is None and external_reference:
            pedido = Pedido.objects.filter(pk=external_reference).first()

        if pedido is not None:
            aplicar_dados_order(pedido, remoto)

        return Response(status=http_status.HTTP_200_OK)

    @extend_schema(summary='Alterar status do pedido', request=PedidoStatusUpdateSerializer)
    @action(
        detail=True,
        methods=['patch'],
        permission_classes=[IsAdminUser],
    )
    def alterar_status(self, request, pk=None):
        with transaction.atomic():
            queryset = self.filter_queryset(self.get_queryset()).select_for_update()
            pedido = get_object_or_404(queryset, pk=pk)
            serializer = PedidoStatusUpdateSerializer(
                pedido,
                data=request.data,
                partial=True,
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()

        return Response(
            self.get_serializer(pedido).data,
            status=http_status.HTTP_200_OK,
        )

    @extend_schema(summary='Obter QR Code de retirada')
    @action(detail=True, methods=['get'])
    def qrcode(self, request, pk=None):
        pedido = self.get_object()
        conteudo = str(pedido.codigo_retirada)
        return Response(
            {
                'codigo_retirada': conteudo,
                'qrcode_base64': gerar_qrcode_base64(conteudo),
            }
        )

    @extend_schema(summary='Retirar pedido via QR Code', request=RetiradaPorQRCodeSerializer)
    @action(
        detail=False,
        methods=['post'],
        permission_classes=[IsAdminUser],
    )
    def retirar_via_qrcode(self, request):
        serializer = RetiradaPorQRCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pedido = serializer.save()
        return Response(
            self.get_serializer(pedido).data,
            status=http_status.HTTP_200_OK,
        )

    @extend_schema(
        summary='Relatório de vendas por período',
        parameters=[
            OpenApiParameter(
                'data_inicio',
                str,
                description='Data inicial no formato YYYY-MM-DD',
                required=True,
            ),
            OpenApiParameter(
                'data_fim',
                str,
                description='Data final no formato YYYY-MM-DD',
                required=True,
            ),
        ],
    )
    @action(
        detail=False,
        methods=['get'],
        permission_classes=[IsAdminUser],
    )
    def relatorio_vendas(self, request):
        data_inicio_str = request.query_params.get('data_inicio')
        data_fim_str = request.query_params.get('data_fim')

        if not data_inicio_str or not data_fim_str:
            return Response(
                {'detail': 'Informe data_inicio e data_fim no formato YYYY-MM-DD.'},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        try:
            data_inicio = date.fromisoformat(data_inicio_str)
            data_fim = date.fromisoformat(data_fim_str)
        except ValueError:
            return Response(
                {'detail': 'Datas em formato inválido. Use YYYY-MM-DD.'},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        if data_inicio > data_fim:
            return Response(
                {'detail': 'data_inicio não pode ser posterior a data_fim.'},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        pedidos_periodo = Pedido.objects.filter(
            status=Pedido.Status.RETIRADO,
            status_atualizado_em__date__gte=data_inicio,
            status_atualizado_em__date__lte=data_fim,
        )
        total_pedidos = pedidos_periodo.count()
        agregado = ItemPedido.objects.filter(
            pedido__in=pedidos_periodo,
        ).aggregate(
            total_vendido=Sum(F('preco_unitario') * F('quantidade')),
        )
        total_vendido = agregado['total_vendido'] or Decimal('0.00')
        ticket_medio = (
            total_vendido / total_pedidos
            if total_pedidos
            else Decimal('0.00')
        )

        return Response(
            {
                'criterio': 'Considera apenas pedidos retirados dentro do período informado.',
                'data_inicio': data_inicio,
                'data_fim': data_fim,
                'total_pedidos': total_pedidos,
                'total_vendido': round(total_vendido, 2),
                'ticket_medio': round(ticket_medio, 2),
            }
        )
