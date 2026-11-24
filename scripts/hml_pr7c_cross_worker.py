"""PR7C — teste de entrega de eventos entre workers ASGI na HML (nunca na produção).

Uso (PowerShell, fora do repositório):
    py -3.12 -m pip install --user websockets
    py -3.12 scripts/hml_pr7c_cross_worker.py --senhas C:/caminho/senhas-hml.env

O arquivo de senhas usa as mesmas chaves do comando redefinir_senhas_hml
(HML_NOVA_SENHA_ADMIN, HML_NOVA_SENHA_CLIENTE_A, HML_NOVA_SENHA_CLIENTE_B).
Nada de token, ticket ou senha é impresso. Efeitos na HML: cria um pedido em
dinheiro fictício do cliente A, envia mensagens no chat dele e o cancela pelo admin
(o cancelamento devolve o estoque).

Prova: o backend roda `uvicorn --workers 2` e responde com `X-HML-Worker` (PID).
Cada conexão WebSocket vive em um único worker; se ações HTTP atendidas pelos dois
PIDs chegam a todas as conexões, ao menos uma delas atravessou workers via Redis.
"""
import argparse
import asyncio
import json
import ssl
import sys
import urllib.error
import urllib.request
import uuid

import websockets

HOST = 'backend-pires-hml.class.fabricadesoftware.ifc.edu.br'
API = f'https://{HOST}/api'
WS_URL = f'wss://{HOST}/ws/v1/events/'
CONTAS = {
    'admin': ('admin.hml@pires.invalid', 'HML_NOVA_SENHA_ADMIN'),
    'cliente_a': ('cliente-a.hml@pires.invalid', 'HML_NOVA_SENHA_CLIENTE_A'),
    'cliente_b': ('cliente-b.hml@pires.invalid', 'HML_NOVA_SENHA_CLIENTE_B'),
}
CONEXOES = {'admin': 3, 'cliente_a': 6, 'cliente_b': 3}
MENSAGENS_CHAT = 5
PIDS = []


def ler_senhas(caminho):
    valores = {}
    with open(caminho, encoding='utf-8') as arquivo:
        for linha in arquivo:
            chave, _, valor = linha.strip().partition('=')
            if chave and valor:
                valores[chave] = valor
    return valores


def http(metodo, rota, token=None, corpo=None):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(f'{API}{rota}', data=dados, method=metodo)
    req.add_header('Accept', 'application/json')
    if dados is not None:
        req.add_header('Content-Type', 'application/json')
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl.create_default_context()) as resp:
            pid = resp.headers.get('X-HML-Worker')
            if pid:
                PIDS.append(pid)
            texto = resp.read().decode() or '{}'
            return resp.status, json.loads(texto)
    except urllib.error.HTTPError as erro:
        return erro.code, {'erro': erro.reason}


def exigir(condicao, mensagem):
    if not condicao:
        print(f'FALHA: {mensagem}')
        sys.exit(1)


async def conectar(token, origem):
    status, corpo = http('POST', '/realtime/ticket/', token, {})
    exigir(status == 200 and corpo.get('ticket'), f'ticket HTTP {status}')
    return await websockets.connect(
        WS_URL,
        subprotocols=['pires.v1', f'pires.ticket.{corpo["ticket"]}'],
        origin=origem,
        open_timeout=20,
    )


async def coletar(conexao, destino):
    try:
        async for texto in conexao:
            destino.append(json.loads(texto))
    except websockets.ConnectionClosed:
        pass


async def principal(args):
    senhas = ler_senhas(args.senhas)
    tokens = {}
    for papel, (email, chave) in CONTAS.items():
        status, corpo = http('POST', '/token/', corpo={'email': email, 'password': senhas.get(chave, '')})
        exigir(status == 200, f'login {papel} HTTP {status}')
        tokens[papel] = corpo['access']
    print('Login das três contas fictícias: OK')

    conexoes, recebidos, tarefas = {}, {}, []
    for papel, quantidade in CONEXOES.items():
        for indice in range(quantidade):
            nome = f'{papel}#{indice + 1}'
            conexoes[nome] = await conectar(tokens[papel], args.origem)
            recebidos[nome] = []
            tarefas.append(asyncio.create_task(coletar(conexoes[nome], recebidos[nome])))
    print(f'WebSockets abertos: {len(conexoes)} (subprotocolo pires.v1)')
    await asyncio.sleep(1)

    _, lista = http('GET', '/produtos/', tokens['cliente_a'])
    produto_id = None
    for item in lista.get('results', lista if isinstance(lista, list) else []):
        _, detalhe = http('GET', f'/produtos/{item["id"]}/', tokens['cliente_a'])
        if detalhe.get('ativo') and (detalhe.get('estoque') or 0) > 0:
            produto_id = item['id']
            break
    exigir(produto_id, 'nenhum produto ativo com estoque na HML')

    status, corpo = http('POST', '/pedidos/checkout_dinheiro/', tokens['cliente_a'], {
        'checkout_id': str(uuid.uuid4()),
        'itens_criacao': [{'produto': produto_id, 'quantidade': 1}],
    })
    exigir(status == 201, f'checkout dinheiro HTTP {status}')
    pedido_id = corpo['pedido']['id']
    try:
        for numero in range(MENSAGENS_CHAT):
            status, _ = http('POST', f'/chat/{pedido_id}/mensagens/', tokens['cliente_a'], {
                'texto': f'PR7C teste multiworker {numero + 1}/{MENSAGENS_CHAT}',
            })
            exigir(status == 201, f'mensagem de chat HTTP {status}')
    finally:
        status, _ = http('PATCH', f'/pedidos/{pedido_id}/alterar_status/', tokens['admin'], {'status': 'cancelado'})
        print(f'Pedido fictício cancelado pelo admin: HTTP {status}')

    await asyncio.sleep(args.espera)
    for conexao in conexoes.values():
        await conexao.close()
    await asyncio.gather(*tarefas)

    def ids(nome, tipos=None):
        return {e['event_id'] for e in recebidos[nome] if tipos is None or e['tipo'] in tipos}

    tipos_pedido_chat = {'pedido.criado', 'pedido.atualizado', 'chat.mensagem_nova'}
    grupos = {papel: [n for n in conexoes if n.startswith(papel)] for papel in CONEXOES}
    referencia_a = ids(grupos['cliente_a'][0], tipos_pedido_chat)
    referencia_admin = ids(grupos['admin'][0], tipos_pedido_chat)
    minimo = 1 + MENSAGENS_CHAT + 1

    print(f'PIDs HTTP distintos: {len(set(PIDS))} em {len(PIDS)} respostas')
    for nome in conexoes:
        print(f'  {nome}: {len(recebidos[nome])} eventos {sorted({e["tipo"] for e in recebidos[nome]})}')

    resultados = {
        'dois workers atenderam HTTP': len(set(PIDS)) >= 2,
        f'cliente A recebeu >= {minimo} eventos de pedido/chat': len(referencia_a) >= minimo,
        'todas as conexões do cliente A receberam os mesmos eventos': all(
            ids(n) == ids(grupos['cliente_a'][0]) for n in grupos['cliente_a']
        ),
        'todas as conexões do admin receberam os mesmos eventos': all(
            ids(n) == ids(grupos['admin'][0]) for n in grupos['admin']
        ),
        'admin recebeu os mesmos eventos de pedido/chat do cliente A': referencia_admin == referencia_a,
        'cliente B não recebeu nada (isolamento)': all(not recebidos[n] for n in grupos['cliente_b']),
    }
    for descricao, ok in resultados.items():
        print(f'{"OK   " if ok else "FALHA"} {descricao}')
    sys.exit(0 if all(resultados.values()) else 1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--senhas', required=True)
    parser.add_argument('--origem', default='http://localhost:5173')
    parser.add_argument('--espera', type=float, default=4.0)
    asyncio.run(principal(parser.parse_args()))
