import socket
import json
import os
from datetime import datetime

HOST = '0.0.0.0'
PORT = 8000
BUFFER = 4096
LOG_FILE = 'server.log'
HISTORY_FILE = 'history.json'

connectedUsers: dict[str, tuple] = {}
messageHistory: list[dict] = []


def loadHistory() -> list[dict]:
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def saveHistory():
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(messageHistory, f, ensure_ascii=False, indent=2)


def writeLog(entry: str):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{timestamp}] {entry}'
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def send(sock: socket.socket, payload: dict, addr: tuple):
    sock.sendto(json.dumps(payload).encode('utf-8'), addr)


def broadcast(sock: socket.socket, payload: dict, exclude: str | None = None):
    for name, addr in connectedUsers.items():
        if name != exclude:
            send(sock, payload, addr)


def handleJoin(sock, data, addr):
    name = data.get('name', '').strip()

    if not name:
        send(sock, {'type': 'error', 'msg': 'Nome inválido.'}, addr)
        return

    if name in connectedUsers:
        send(sock, {'type': 'error', 'msg': f'Nome "{name}" já está em uso.'}, addr)
        return

    connectedUsers[name] = addr
    writeLog(f'CONNECT  {name} ({addr[0]}:{addr[1]})')

    send(sock, {
        'type': 'welcome',
        'name': name,
        'users': list(connectedUsers.keys()),
        'history': messageHistory[-50:] 
    }, addr)

    broadcast(sock, {
        'type': 'system',
        'msg': f'*** {name} entrou no chat. ***',
        'users': list(connectedUsers.keys())
    }, exclude=name)


def handleMessage(sock, data, addr):
    name = data.get('name', '')
    text = data.get('text', '').strip()

    if name not in connectedUsers or connectedUsers[name] != addr:
        send(sock, {'type': 'error', 'msg': 'Usuário não autenticado.'}, addr)
        return

    entry = {
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'from': name,
        'text': text
    }
    messageHistory.append(entry)
    saveHistory()
    writeLog(f'MSG      [{name}] {text}')

    broadcast(sock, {'type': 'message', **entry})


def handlePrivate(sock, data, addr):
    sender = data.get('name', '')
    target = data.get('to', '').strip()
    text   = data.get('text', '').strip()

    if sender not in connectedUsers or connectedUsers[sender] != addr:
        send(sock, {'type': 'error', 'msg': 'Usuário não autenticado.'}, addr)
        return

    if target not in connectedUsers:
        send(sock, {'type': 'error', 'msg': f'Usuário "{target}" não encontrado.'}, addr)
        return

    timestamp = datetime.now().strftime('%H:%M:%S')
    writeLog(f'PRIVATE  [{sender}] → [{target}] {text}')

    payload = {
        'type': 'private',
        'timestamp': timestamp,
        'from': sender,
        'to': target,
        'text': text
    }
    send(sock, payload, connectedUsers[target])
    send(sock, payload, addr)


def handleList(sock, data, addr):
    send(sock, {
        'type': 'user_list',
        'users': list(connectedUsers.keys())
    }, addr)


def handleQuit(sock, data, addr):
    name = data.get('name', '')
    if name in connectedUsers:
        del connectedUsers[name]
        writeLog(f'DISCONNECT {name}')
        broadcast(sock, {
            'type': 'system',
            'msg': f'*** {name} saiu do chat. ***',
            'users': list(connectedUsers.keys())
        })


def startServer():
    global messageHistory
    messageHistory = loadHistory()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, PORT))
    writeLog(f'STARTUP  Servidor UDP iniciado em {HOST}:{PORT}')

    handlers = {
        'join':    handleJoin,
        'message': handleMessage,
        'private': handlePrivate,
        'list':    handleList,
        'quit':    handleQuit,
    }

    while True:
        try:
            raw, addr = sock.recvfrom(BUFFER)
            data = json.loads(raw.decode('utf-8'))
            msg_type = data.get('type', '')
            handler = handlers.get(msg_type)
            if handler:
                handler(sock, data, addr)
            else:
                writeLog(f'UNKNOWN  tipo={msg_type} de {addr}')
        except json.JSONDecodeError:
            writeLog(f'INVALID  pacote malformado de {addr}')
        except KeyboardInterrupt:
            writeLog('SHUTDOWN Servidor encerrado.')
            break


if __name__ == '__main__':
    startServer()