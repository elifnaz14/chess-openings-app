import json
import shutil
import sys
from pathlib import Path

import chess
import chess.engine

DATA_DIR = Path("data")
INPUT_FILE = DATA_DIR / "openings.json"
OUTPUT_FILE = DATA_DIR / "openings_eval.json"
DEPTH = 12  # Analiz derinliği. Yüksek = daha doğru ama daha yavaş.


def find_stockfish():
    path = shutil.which("stockfish")
    if path is None:
        for candidate in ["/opt/homebrew/bin/stockfish", "/usr/local/bin/stockfish", "/usr/games/stockfish"]:
            if Path(candidate).exists():
                return candidate
        print("Stockfish bulunamadı. Önce kurulumu yapmalısın.")
        sys.exit(1)
    return path


def main():
    limit_count = int(sys.argv[1]) if len(sys.argv) > 1 else None
    with open(INPUT_FILE, encoding="utf-8") as f:
        openings = json.load(f)
    if limit_count:
        openings = openings[:limit_count]

    engine = chess.engine.SimpleEngine.popen_uci(find_stockfish())
    total = len(openings)
    try:
        for i, opening in enumerate(openings, start=1):
            board = chess.Board(opening["fen"])
            info = engine.analyse(board, chess.engine.Limit(depth=DEPTH))
            score = info["score"].white().score(mate_score=10000)
            opening["eval_cp"] = score
            if i % 100 == 0 or i == total:
                print(f"{i}/{total} açılış değerlendirildi...")
    finally:
        engine.quit()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(openings, f, ensure_ascii=False, indent=2)

    evals = [o["eval_cp"] for o in openings]
    print()
    print("ÖZET (skorlar beyaz açısından, 100 = yaklaşık 1 piyon):")
    print(f"  En düşük: {min(evals)}  En yüksek: {max(evals)}")
    for label, cond in [
        ("+50 ve üzeri (beyaz belirgin iyi)", lambda x: x >= 50),
        ("+20 ile +49", lambda x: 20 <= x < 50),
        ("-19 ile +19 (dengeli)", lambda x: -19 <= x < 20),
        ("-20 ile -49", lambda x: -50 < x <= -20),
        ("-50 ve altı (siyah belirgin iyi)", lambda x: x <= -50),
    ]:
        print(f"  {label}: {sum(1 for x in evals if cond(x))}")
    print(f"Sonuç dosyası: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
