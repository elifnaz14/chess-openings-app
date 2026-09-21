import json
from pathlib import Path

DATA_DIR = Path("data")
INPUT_FILE = DATA_DIR / "openings_final.json"
OUTPUT_FILE = DATA_DIR / "openings_app.json"

TEMPO_BONUS = 25  # label_advantage.py ile aynı değer (sıra bonusu düzeltmesi)

KEEP_FIELDS = ["id", "eco", "name", "pgn", "fen", "side_to_move", "structure"]


def advantage_in_pawns(opening):
    """Motor skorunu sıra bonusundan arındırıp piyon cinsinden döndürür.
    Pozitif = beyaz üstün, negatif = siyah üstün."""
    cp = opening["eval_cp"]
    if opening["side_to_move"] == "white":
        cp -= TEMPO_BONUS
    else:
        cp += TEMPO_BONUS
    return round(cp / 100, 2)


def main():
    with open(INPUT_FILE, encoding="utf-8") as f:
        openings = json.load(f)

    app_openings = []
    for o in openings:
        if not o["playable"]:
            continue
        item = {key: o[key] for key in KEEP_FIELDS}
        item["advantage_pawns"] = advantage_in_pawns(o)
        app_openings.append(item)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(app_openings, f, ensure_ascii=False, indent=2)

    values = [o["advantage_pawns"] for o in app_openings]
    print(f"Uygulama için {len(app_openings)} açılış hazırlandı.")
    print(f"Üstünlük aralığı: {min(values)} ile {max(values)} piyon")
    print(f"Sonuç dosyası: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
