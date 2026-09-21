import csv
import io
import json
from pathlib import Path

import chess
import chess.pgn

DATA_DIR = Path("data")
OUTPUT_FILE = DATA_DIR / "openings.json"


def board_from_pgn(pgn_text):
    """Hamle dizisini oynatıp son pozisyonu (tahta) döndürür."""
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    board = game.board()
    for move in game.mainline_moves():
        board.push(move)
    return board


def main():
    openings = []
    for letter in "abcde":
        file_path = DATA_DIR / f"{letter}.tsv"
        with open(file_path, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                board = board_from_pgn(row["pgn"])
                openings.append(
                    {
                        "id": len(openings) + 1,
                        "eco": row["eco"],
                        "name": row["name"],
                        "pgn": row["pgn"],
                        "fen": board.fen(),
                        "ply": len(board.move_stack),
                        "side_to_move": "white" if board.turn else "black",
                    }
                )

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(openings, f, ensure_ascii=False, indent=2)

    print(f"Toplam {len(openings)} açılış işlendi.")
    print(f"Sonuç dosyası: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
