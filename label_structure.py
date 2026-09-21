import json
from pathlib import Path

import chess

DATA_DIR = Path("data")
INPUT_FILE = DATA_DIR / "openings_labeled.json"
OUTPUT_FILE = DATA_DIR / "openings_final.json"

OPEN_THRESHOLD = 9     # Bu puan ve üzeri: açık pozisyon
CLOSED_THRESHOLD = 0   # Bu puan ve altı: kapalı pozisyon
CENTER_FILES = (2, 3, 4, 5)  # c, d, e, f dosyaları


def openness_score(fen):
    """Pozisyonun piyon yapısına bakarak 'açıklık' puanı hesaplar.
    Yüksek puan = açık, düşük puan = kapalı."""
    board = chess.Board(fen)
    white_pawns = list(board.pieces(chess.PAWN, True))
    black_pawns = list(board.pieces(chess.PAWN, False))
    total_pawns = len(white_pawns) + len(black_pawns)

    center_open = 0   # Merkezde hiç piyon olmayan dosyalar
    center_half = 0   # Merkezde sadece bir tarafın piyonu olan dosyalar
    for file_index in CENTER_FILES:
        has_white = any(chess.square_file(s) == file_index for s in white_pawns)
        has_black = any(chess.square_file(s) == file_index for s in black_pawns)
        if not has_white and not has_black:
            center_open += 1
        elif has_white != has_black:
            center_half += 1

    # Kilitli piyonlar: bir piyonun hemen önünde rakip piyon varsa kilitlidir
    locked_total = 0
    locked_center = 0
    black_set = set(black_pawns)
    for square in white_pawns:
        ahead = square + 8
        if ahead < 64 and ahead in black_set:
            locked_total += 1
            if chess.square_file(square) in CENTER_FILES:
                locked_center += 1

    # d ve e dosyalarındaki piyon sayısı (başlangıçta 4)
    d_e_pawns = sum(
        1 for s in white_pawns + black_pawns if chess.square_file(s) in (3, 4)
    )

    score = (
        3 * (16 - total_pawns)                # Takas edilen her piyon açıklığı artırır
        + 2 * center_open                     # Piyonsuz merkez dosyaları
        + 1 * center_half                     # Yarı açık merkez dosyaları
        - 2 * locked_center                   # Kilitli merkez piyonları kapalılık getirir
        - 1 * (locked_total - locked_center)  # Kenardaki kilitli piyonlar
        + 1.5 * (4 - d_e_pawns)               # d/e piyonları takas edildiyse daha açık
    )
    return score


def main():
    with open(INPUT_FILE, encoding="utf-8") as f:
        openings = json.load(f)

    for o in openings:
        score = openness_score(o["fen"])
        o["openness_score"] = score
        if score >= OPEN_THRESHOLD:
            o["structure"] = "open"
        elif score <= CLOSED_THRESHOLD:
            o["structure"] = "closed"
        else:
            o["structure"] = "semi"

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(openings, f, ensure_ascii=False, indent=2)

    playable = [o for o in openings if o["playable"]]
    print(f"Oynanabilir açılış: {len(playable)}")
    for key, label in [("open", "Açık"), ("semi", "Yarı açık/kapalı"), ("closed", "Kapalı")]:
        print(f"  {label}: {sum(1 for o in playable if o['structure'] == key)}")

    print()
    print("Filtre kombinasyonları (oynanabilir açılış sayısı):")
    for structure, s_label in [("open", "Açık"), ("closed", "Kapalı")]:
        for adv, a_label in [("white", "Beyaza üstünlük"), ("black", "Siyaha üstünlük")]:
            count = sum(
                1 for o in playable if o["structure"] == structure and o["advantage"] == adv
            )
            print(f"  {s_label} + {a_label}: {count}")
    print(f"Sonuç dosyası: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
