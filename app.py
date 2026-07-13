import os
import random
import string
from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, leave_room, emit

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "clave-secreta-tictactoe3d")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

SIZE = 4


# ---------------------------------------------------------------------------
# Logica del juego: tablero 4x4x4. Indice de celda = z*16 + y*4 + x
# (misma convencion que el programa original en Tkinter)
# ---------------------------------------------------------------------------

def cell_index(x, y, z):
    return z * 16 + y * 4 + x


def build_winning_lines():
    """Genera las 76 lineas ganadoras posibles de un cubo 4x4x4."""
    lines = []

    def push(coords):
        lines.append([cell_index(x, y, z) for (x, y, z) in coords])

    r = range(SIZE)

    # Lineas rectas a lo largo de X, Y, Z
    for z in r:
        for y in r:
            push([(x, y, z) for x in r])  # eje X
    for z in r:
        for x in r:
            push([(x, y, z) for y in r])  # eje Y
    for y in r:
        for x in r:
            push([(x, y, z) for z in r])  # eje Z

    # Diagonales dentro de cada capa Z (plano XY)
    for z in r:
        push([(i, i, z) for i in r])
        push([(i, 3 - i, z) for i in r])
    # Diagonales dentro de cada capa Y (plano XZ)
    for y in r:
        push([(i, y, i) for i in r])
        push([(i, y, 3 - i) for i in r])
    # Diagonales dentro de cada capa X (plano YZ)
    for x in r:
        push([(x, i, i) for i in r])
        push([(x, i, 3 - i) for i in r])

    # 4 diagonales espaciales (de esquina a esquina del cubo)
    push([(i, i, i) for i in r])
    push([(i, i, 3 - i) for i in r])
    push([(i, 3 - i, i) for i in r])
    push([(3 - i, i, i) for i in r])

    return lines


WINNING_LINES = build_winning_lines()  # 76 lineas


def check_winner(board):
    for line in WINNING_LINES:
        first = board[line[0]]
        if first and all(board[i] == first for i in line):
            return first, line
    return None, None


def board_full(board):
    return all(cell is not None for cell in board)


# ---------------------------------------------------------------------------
# Gestion de salas (en memoria)
# ---------------------------------------------------------------------------

rooms = {}  # code -> room dict
CODE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin 0/O/1/I para evitar confusion


def make_room_code():
    while True:
        code = "".join(random.choice(CODE_CHARS) for _ in range(4))
        if code not in rooms:
            return code


def fresh_board():
    return [None] * 64


def new_room():
    code = make_room_code()
    room = {
        "code": code,
        "board": fresh_board(),
        "turn": "X",
        "players": [],  # {sid, name, symbol, connected}
        "winner": None,
        "win_line": None,
        "draw": False,
        "rematch": set(),
    }
    rooms[code] = room
    return room


def public_state(room):
    return {
        "code": room["code"],
        "board": room["board"],
        "turn": room["turn"],
        "players": [
            {"name": p["name"], "symbol": p["symbol"], "connected": p["connected"]}
            for p in room["players"]
        ],
        "winner": room["winner"],
        "winLine": room["win_line"],
        "draw": room["draw"],
        "started": len(room["players"]) == 2,
    }


def broadcast(room):
    socketio.emit("state", public_state(room), room=room["code"])


def reset_board(room):
    room["board"] = fresh_board()
    room["turn"] = "X"
    room["winner"] = None
    room["win_line"] = None
    room["draw"] = False
    room["rematch"] = set()


def find_room_by_sid(sid):
    code = getattr(find_room_by_sid, "_map", {}).get(sid)
    return rooms.get(code) if code else None


sid_room_map = {}  # sid -> room code


# ---------------------------------------------------------------------------
# Rutas HTTP
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# Eventos Socket.IO
# ---------------------------------------------------------------------------

@socketio.on("create_room")
def on_create_room(data):
    name = (data or {}).get("name") or "Jugador 1"
    room = new_room()
    player = {"sid": request.sid, "name": name[:20], "symbol": "X", "connected": True}
    room["players"].append(player)
    join_room(room["code"])
    sid_room_map[request.sid] = room["code"]
    emit("create_room_ack", {"ok": True, "roomCode": room["code"], "symbol": "X"})
    broadcast(room)


@socketio.on("join_room_event")
def on_join_room(data):
    data = data or {}
    code = (data.get("roomCode") or "").upper().strip()
    name = data.get("name") or ""
    room = rooms.get(code)
    if not room:
        emit("join_room_ack", {"ok": False, "error": "No existe una sala con ese codigo."})
        return

    disconnected_slot = next((p for p in room["players"] if not p["connected"]), None)
    if len(room["players"]) >= 2 and not disconnected_slot:
        emit("join_room_ack", {"ok": False, "error": "Esa sala ya tiene dos jugadores."})
        return

    if disconnected_slot:
        disconnected_slot["sid"] = request.sid
        disconnected_slot["connected"] = True
        if name:
            disconnected_slot["name"] = name[:20]
        player = disconnected_slot
    else:
        symbol = "X" if len(room["players"]) == 0 else "O"
        player = {
            "sid": request.sid,
            "name": (name or f"Jugador {'1' if symbol == 'X' else '2'}")[:20],
            "symbol": symbol,
            "connected": True,
        }
        room["players"].append(player)

    join_room(room["code"])
    sid_room_map[request.sid] = room["code"]
    emit("join_room_ack", {"ok": True, "roomCode": room["code"], "symbol": player["symbol"]})
    broadcast(room)


@socketio.on("move")
def on_move(data):
    code = sid_room_map.get(request.sid)
    room = rooms.get(code)
    if not room:
        return
    player = next((p for p in room["players"] if p["sid"] == request.sid), None)
    if not player or len(room["players"]) < 2:
        return
    if room["winner"] or room["draw"]:
        return
    if player["symbol"] != room["turn"]:
        return

    try:
        x, y, z = int(data["x"]), int(data["y"]), int(data["z"])
    except (KeyError, TypeError, ValueError):
        return
    if not all(0 <= v < SIZE for v in (x, y, z)):
        return

    idx = cell_index(x, y, z)
    if room["board"][idx] is not None:
        return

    room["board"][idx] = player["symbol"]

    winner, line = check_winner(room["board"])
    if winner:
        room["winner"] = winner
        room["win_line"] = line
    elif board_full(room["board"]):
        room["draw"] = True
    else:
        room["turn"] = "O" if room["turn"] == "X" else "X"

    broadcast(room)


@socketio.on("request_rematch")
def on_request_rematch():
    code = sid_room_map.get(request.sid)
    room = rooms.get(code)
    if not room:
        return
    player = next((p for p in room["players"] if p["sid"] == request.sid), None)
    if not player:
        return
    room["rematch"].add(player["symbol"])
    if len(room["players"]) == 2 and len(room["rematch"]) == 2:
        reset_board(room)
    broadcast(room)
    if len(room["rematch"]) == 1:
        socketio.emit("rematch_requested", {"by": player["symbol"]}, room=room["code"])


@socketio.on("leave_room_event")
def on_leave_room():
    handle_leave(request.sid)


@socketio.on("disconnect")
def on_disconnect():
    handle_leave(request.sid)


def handle_leave(sid):
    code = sid_room_map.get(sid)
    if not code:
        return
    room = rooms.get(code)
    if not room:
        return
    player = next((p for p in room["players"] if p["sid"] == sid), None)
    if player:
        player["connected"] = False
        room["rematch"].discard(player["symbol"])
    leave_room(code, sid=sid)
    sid_room_map.pop(sid, None)
    if all(not p["connected"] for p in room["players"]):
        rooms.pop(code, None)  # sala vacia, se elimina
    else:
        broadcast(room)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)
