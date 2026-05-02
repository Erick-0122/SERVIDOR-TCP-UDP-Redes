import socket
import json
import threading

HOST = '192.168.100.103'
PORT = 8000
BUFFER = 4096

myName: str = ''
sock: socket.socket | None = None
running = True


def send(payload: dict):
    sock.sendto(json.dumps(payload).encode('utf-8'), (HOST, PORT))


def receiver():
    global running
    while running:
        try:
            raw, _ = sock.recvfrom(BUFFER)
            data = json.loads(raw.decode('utf-8'))
            render(data)
        except OSError:
            break
        except Exception as e:
            print(f'\n[erro interno] {e}')


def render(data: dict):
    t = data.get('type')

    if t == 'welcome':
        print(f"\nBem-vindo, {data['name']}!")
        print(f"Usuários online: {', '.join(data['users'])}")
        if data.get('history'):
            print('\n── Histórico recente ──')
            for m in data['history']:
                print(f"  [{m['timestamp']}] {m['from']}: {m['text']}")
            print('── fim do histórico ──\n')

    elif t == 'message':
        print(f"\n[{data['timestamp']}] {data['from']}: {data['text']}")

    elif t == 'private':
        direction = '→ para você' if data['to'] == myName else f'→ {data["to"]}'
        print(f"\n[{data['timestamp']}] {data['from']} (privado {direction}): {data['text']}")

    elif t == 'system':
        users = data.get('users', [])
        print(f"\n  {data['msg']}")
        if users:
            print(f"Online agora: {', '.join(users)}")

    elif t == 'user_list':
        print(f"\nUsuários online: {', '.join(data['users'])}")

    elif t == 'error':
        print(f"\n{data['msg']}")

    printPrompt()


def printPrompt():
    print(f'[{myName}] > ', end='', flush=True)


HELP = """
Comandos disponíveis:
  /list              – lista usuários conectados
  /msg <nome> <texto> – mensagem privada
  /quit              – sair do chat
  /help              – esta ajuda
  <texto>            – mensagem pública
"""


def main():
    global myName, sock, running

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', 0))

    while True:
        myName = input('Seu nome: ').strip()
        if myName:
            break
        print('Nome não pode ser vazio.')

    t = threading.Thread(target=receiver, daemon=True)
    t.start()

    send({'type': 'join', 'name': myName})

    print(HELP)
    printPrompt()

    try:
        while running:
            line = input()

            if not line.strip():
                printPrompt()
                continue

            if line.startswith('/quit'):
                send({'type': 'quit', 'name': myName})
                print('Até mais! 👋')
                running = False
                break

            elif line.startswith('/list'):
                send({'type': 'list', 'name': myName})

            elif line.startswith('/msg '):
                parts = line[5:].split(' ', 1)
                if len(parts) < 2:
                    print('Uso: /msg <nome> <texto>')
                    printPrompt()
                    continue
                target, text = parts
                send({
                    'type': 'private',
                    'name': myName,
                    'to': target.strip(),
                    'text': text.strip()
                })

            elif line.startswith('/help'):
                print(HELP)
                printPrompt()

            else:
                send({
                    'type': 'message',
                    'name': myName,
                    'text': line.strip()
                })

    except KeyboardInterrupt:
        send({'type': 'quit', 'name': myName})
        print('\nDesconectado.')
    finally:
        sock.close()


if __name__ == '__main__':
    main()