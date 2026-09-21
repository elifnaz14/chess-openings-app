import json
import statistics
from pathlib import Path

import chess

DATA_DIR = Path("data")
INPUT_FILE = DATA_DIR / "openings_eval.json"
OUTPUT_FILE = DATA_DIR / "openings_labeled.json"

TEMPO_BONUS = 25      # Sırası olan tarafa motorun verdiği küçük bonusu düzeltir
THRESHOLD = 25        # "Üstünlük" sayılması için normalden sapma miktarı
MIN_PLY = 8           # Bundan kısa açılışlar (yarım hamle) oyun ortası sayılmaz
MAX_ABS_EVAL = 150    # Bu kadar dengesiz pozisyonlar adil bir başlangıç değildir


def main():
    with open(INPUT_FILE, encoding="utf-8") as f:
        openings = json.load(f)

    # Tempo düzeltmesi: sıra beyazdaysa beyaz bonus almıştır, siyahtaysa siyah.
    for o in openings:
        if o["side_to_move"] == "white":
            o["_adj"] = o["eval_cp"] - TEMPO_BONUS
        else:
            o["_adj"] = o["eval_cp"] + TEMPO_BONUS

    # "Normal" seviye: tüm açılışların ortanca skoru (beyazın doğal ilk hamle avantajı)
    median = statistics.median(o["_adj"] for o in openings)

    for o in openings:
        relative = o["_adj"] - median
        o["eval_relative"] = round(relative)
        del o["_adj"]

        if relative >= THRESHOLD:
            o["advantage"] = "white"
        elif relative <= -THRESHOLD:
            o["advantage"] = "black"
        else:
            o["advantage"] = "balanced"

        game_over = chess.Board(o["fen"]).is_game_over()
        o["playable"] = (
            not game_over
            and o["ply"] >= MIN_PLY
            and abs(o["eval_cp"]) <= MAX_ABS_EVAL
        )

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(openings, f, ensure_ascii=False, indent=2)

    playable = [o for o in openings if o["playable"]]
    print(f"Normal seviye (ortanca skor): {round(median)}")
    print(f"Toplam açılış: {len(openings)}")
    print(f"Oynanabilir açılış: {len(playable)}")
    for key, label in [("white", "Beyaza üstünlük"), ("black", "Siyaha üstünlük"), ("balanced", "Dengeli")]:
        count = sum(1 for o in playable if o["advantage"] == key)
        print(f"  {label}: {count}")
    print(f"Sonuç dosyası: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
