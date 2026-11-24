"""Somente HML (branch deploy/pr6-hml-asgi): identifica o processo que respondeu.

O teste PR7C precisa provar que eventos publicados por um worker ASGI chegam a
conexões WebSocket de outro worker via Redis. O cabeçalho expõe apenas o PID do
processo, sem dados de usuário, Redis ou ambiente. Nunca portar para dev/main.
"""
import os


class HmlWorkerHeaderMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['X-HML-Worker'] = str(os.getpid())
        return response
