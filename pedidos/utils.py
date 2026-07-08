"""
Geração de QR Code para retirada de pedidos.
"""

import base64
from io import BytesIO

import qrcode


def gerar_qrcode_base64(conteudo: str) -> str:
    """Gera um QR Code a partir de um texto e retorna como data URI (PNG em base64).

    O retorno já vem pronto para ser usado direto num <img src="..."> no
    frontend, sem precisar de nenhum endpoint de arquivo estático.
    """
    imagem = qrcode.make(conteudo)
    buffer = BytesIO()
    imagem.save(buffer, format='PNG')
    imagem_base64 = base64.b64encode(buffer.getvalue()).decode('ascii')
    return f'data:image/png;base64,{imagem_base64}'
