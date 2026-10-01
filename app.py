import io
import json
import math
import random
import certifi
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import chess
import chess.pgn
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

DATA_FILE = Path(__file__).parent / "data" / "openings_app.json"

with open(DATA_FILE, encoding="utf-8") as f:
    OPENINGS = json.load(f)

OPENINGS_BY_ID = {o["id"]: o for o in OPENINGS}
HISTORY_CACHE = {}

VALID_STRUCTURES = {"open", "closed"}
ADV_LIMIT = 1.5        # Slider'ın uç değerleri (piyon). Uçlar "sınırsız" sayılır.
ADV_TOLERANCE = 0.05   # Slider adımı 0,1 olduğu için yarım adım pay bırakılır.

def get_opening_history(opening):
    """Açılışın hamle dizisini ve her adımın tahta durumunu hesaplar."""
    oid = opening["id"]
    if oid in HISTORY_CACHE:
        return HISTORY_CACHE[oid]

    game = chess.pgn.read_game(io.StringIO(opening["pgn"]))
    board = game.board()
    start_fen = board.fen()
    moves = []

    for move in game.mainline_moves():
        san = board.san(move)
        from_sq = chess.square_name(move.from_square)
        to_sq = chess.square_name(move.to_square)
        is_capture = board.is_capture(move)
        is_castling = board.is_castling(move)
        is_en_passant = board.is_en_passant(move)
        promotion = chess.piece_symbol(move.promotion) if move.promotion else None

        castling_rook = None
        if is_castling:
            if to_sq == "g1": castling_rook = {"from": "h1", "to": "f1"}
            elif to_sq == "c1": castling_rook = {"from": "a1", "to": "d1"}
            elif to_sq == "g8": castling_rook = {"from": "h8", "to": "f8"}
            elif to_sq == "c8": castling_rook = {"from": "a8", "to": "d8"}

        captured_square = None
        if is_capture:
            if is_en_passant:
                captured_square = to_sq[0] + from_sq[1]
            else:
                captured_square = to_sq

        board.push(move)
        moves.append({
            "san": san,
            "uci": move.uci(),
            "from": from_sq,
            "to": to_sq,
            "fen": board.fen(),
            "capture": is_capture,
            "captured_square": captured_square,
            "castling": is_castling,
            "castling_rook": castling_rook,
            "en_passant": is_en_passant,
            "promotion": promotion,
        })

    data = {
        "start_fen": start_fen,
        "history": moves,
    }
    HISTORY_CACHE[oid] = data
    return data


LICHESS_OPEN_CHALLENGE_URL = "https://lichess.org/api/challenge/open"
LICHESS_PREFIX = "https://lichess.org/"

# Süre seçenekleri: anahtar -> (başlangıç süresi saniye, hamle başına eklenen saniye). None = saatsiz.
# Lichess'in Bullet / Blitz / Rapid / Classical kategorilerindeki standart süreler.
TIME_CONTROLS = {
    "1+0": (60, 0),
    "2+1": (120, 1),
    "3+0": (180, 0),
    "3+2": (180, 2),
    "5+0": (300, 0),
    "5+3": (300, 3),
    "10+0": (600, 0),
    "10+5": (600, 5),
    "15+10": (900, 10),
    "30+0": (1800, 0),
    "30+20": (1800, 20),
    "none": None,
}


def read_number(name, default):
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


@app.route("/")
def home():
    opening_id = request.args.get("id")
    initial_opening = None
    if opening_id:
        try:
            oid = int(opening_id)
            if oid in OPENINGS_BY_ID:
                raw = dict(OPENINGS_BY_ID[oid])
                raw.update(get_opening_history(raw))
                initial_opening = raw
        except ValueError:
            pass
    initial_mode = request.args.get("mode")
    initial_fen = request.args.get("fen")
    return render_template(
        "index.html",
        initial_opening=initial_opening,
        initial_mode=initial_mode,
        initial_fen=initial_fen,
    )


@app.route("/api/opening/<int:opening_id>")
def get_opening(opening_id):
    if opening_id not in OPENINGS_BY_ID:
        return jsonify(error="Opening not found"), 404
    raw = dict(OPENINGS_BY_ID[opening_id])
    raw.update(get_opening_history(raw))
    return jsonify(opening=raw)



@app.route("/api/random-opening")
def random_opening():
    structure = request.args.get("structure", "any")
    min_adv = read_number("min_adv", -ADV_LIMIT)
    max_adv = read_number("max_adv", ADV_LIMIT)

    if structure != "any" and structure not in VALID_STRUCTURES:
        return jsonify(error="structure must be open or closed"), 400
    if min_adv is None or max_adv is None:
        return jsonify(error="min_adv and max_adv must be numbers"), 400
    if min_adv > max_adv:
        min_adv, max_adv = max_adv, min_adv

    lower = None if min_adv <= -ADV_LIMIT + 1e-9 else min_adv - ADV_TOLERANCE
    upper = None if max_adv >= ADV_LIMIT - 1e-9 else max_adv + ADV_TOLERANCE

    candidates = [
        o
        for o in OPENINGS
        if (structure == "any" or o["structure"] == structure)
        and (lower is None or o["advantage_pawns"] >= lower)
        and (upper is None or o["advantage_pawns"] <= upper)
    ]

    if not candidates:
        return jsonify(error="No opening matches these filters"), 404

    chosen = random.choice(candidates)
    opening_data = dict(chosen)
    opening_data.update(get_opening_history(chosen))
    return jsonify(opening=opening_data, pool_size=len(candidates))


@app.route("/api/create-game", methods=["POST"])
def create_game():
    """Seçilen açılış veya özel FEN pozisyonundan Lichess'te iki kişilik açık bir oyun oluşturur."""
    payload = request.get_json(silent=True) or {}
    opening_id = payload.get("opening_id")
    custom_fen = payload.get("fen")
    time_key = payload.get("time_control", "10+0")

    if time_key not in TIME_CONTROLS:
        return jsonify(error="Unknown time control"), 400

    fen = None
    game_name = "go2mid.com game"
    if opening_id is not None:
        opening = OPENINGS_BY_ID.get(opening_id)
        if opening is None:
            return jsonify(error="Unknown opening"), 400
        fen = opening["fen"]
        game_name = ("go2mid.com: " + opening["name"].split(":")[0])[:50]
    elif custom_fen:
        try:
            b = chess.Board(custom_fen)
            fen = b.fen()
            game_name = "go2mid.com: Piece Odds"
        except (ValueError, AssertionError):
            return jsonify(error="Invalid FEN"), 400
    else:
        return jsonify(error="Missing opening_id or fen"), 400

    form = {
        "variant": "fromPosition",
        "fen": fen,
        "rated": "false",
        "name": game_name,
    }
    clock = TIME_CONTROLS[time_key]
    if clock is not None:
        form["clock.limit"] = str(clock[0])
        form["clock.increment"] = str(clock[1])

    lichess_request = urllib.request.Request(
        LICHESS_OPEN_CHALLENGE_URL,
        data=urllib.parse.urlencode(form).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": "go2mid.com/1.0 (chess opening randomizer)",
        },
    )

    try:
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(lichess_request, timeout=10, context=ssl_context) as response:
            body = json.load(response)
    except urllib.error.HTTPError as err:
        app.logger.warning("Lichess returned HTTP %s: %s", err.code, err.read()[:300])
        status = 429 if err.code == 429 else 502
        return jsonify(error="Lichess could not create the game"), status
    except (urllib.error.URLError, TimeoutError, ValueError) as err:
        app.logger.warning("Could not reach Lichess: %s", err)
        return jsonify(error="Could not reach Lichess"), 502

    challenge = body.get("challenge", body)
    url = challenge.get("url")
    url_white = challenge.get("urlWhite")
    url_black = challenge.get("urlBlack")

    links = [url, url_white, url_black]
    if not all(isinstance(link, str) and link.startswith(LICHESS_PREFIX) for link in links):
        app.logger.warning("Unexpected Lichess response: %s", str(body)[:300])
        return jsonify(error="Unexpected response from Lichess"), 502

    return jsonify(url=url, url_white=url_white, url_black=url_black)


if __name__ == "__main__":
    app.run(debug=True, port=5001)
