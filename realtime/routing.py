"""Rotas ASGI restritas; não há WebSocket público sem ticket."""
from django.urls import path

from .consumers import EventsConsumer

websocket_urlpatterns = [
    path('ws/v1/events/', EventsConsumer.as_asgi()),
]
