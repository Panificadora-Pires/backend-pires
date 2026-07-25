from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from catalogo.views import CategoriaViewSet, ProdutoViewSet, PromocaoViewSet
from core.views import (
    AdminInviteCreateView,
    AdminInviteRegistrationView,
    CustomGoogleLoginView,
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    CustomTokenVerifyView,
    UserRegistrationView,
    UserViewSet,
)
from notificacoes.views import NotificacaoViewSet
from pedidos.views import PedidoViewSet

router = DefaultRouter()

router.register(r'usuarios', UserViewSet, basename='usuarios')
router.register(r'categorias', CategoriaViewSet, basename='categorias')
router.register(r'produtos', ProdutoViewSet, basename='produtos')
router.register(r'promocoes', PromocaoViewSet, basename='promocoes')
router.register(r'pedidos', PedidoViewSet, basename='pedidos')
router.register(r'notificacoes', NotificacaoViewSet, basename='notificacoes')

urlpatterns = [
    path('admin/', admin.site.urls),

    # OpenAPI 3
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/doc/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Autenticação JWT
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/verify/', CustomTokenVerifyView.as_view(), name='token_verify'),

    # Registro de alunos
    path('api/registro/', UserRegistrationView.as_view(), name='user_registration'),

    # Login social (Google) — recebe o ID Token do frontend
    path('api/social/google/', CustomGoogleLoginView.as_view(), name='google_login'),

    # Convites de administrador
    path('api/admin-convites/', AdminInviteCreateView.as_view(), name='admin_invite_create'),
    path('api/admin-cadastro/', AdminInviteRegistrationView.as_view(), name='admin_invite_register'),

    # API Router principal
    path('api/', include(router.urls)),
]
