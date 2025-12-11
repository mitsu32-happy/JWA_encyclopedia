# scripts/update_creature_rarity_class.py
import json
import time
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT_DIR / "data" / "creatures_master_ja.json"
BACKUP_FILE = ROOT_DIR / "data" / "creatures_master_ja_backup_classification.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0 Safari/537.36"
}


def extract_classification(html: str):
    """
    paleo.gg の恐竜詳細ページから
    Rarity / Class を抜き出す。
    取得できなかった場合は (None, None) を返す。
    """
    soup = BeautifulSoup(html, "html.parser")

    rarity = None
    clazz = None

    # --- パターン1: <dl><dt>Rarity</dt><dd>Epic</dd> 形式 ----------
    for dl in soup.find_all("dl"):
        for dt in dl.find_all("dt"):
            label = dt.get_text(strip=True)
            dd = dt.find_next_sibling("dd")
            if not dd:
                continue
            value = dd.get_text(" ", strip=True)

            if label == "Rarity" and not rarity:
                rarity = value
            elif label == "Class" and not clazz:
                clazz = value

    # --- パターン2: テキスト全体からのフォールバック ----------
    if not (rarity and clazz):
        text = soup.get_text(" ", strip=True)

        if not rarity:
            m = re.search(r"Rarity\s+([A-Za-z]+)", text)
            if m:
                rarity = m.group(1)

        if not clazz:
            # 「Class XXX YYY Rarity」みたいな並びを想定して抽出
            m = re.search(
                r"Class\s+([A-Za-z ]+?)(?:\s+Family|\s+Size|\s+Diet|\s+Rarity|\s+Abilities|\s+Stats|$)",
                text,
            )
            if m:
                clazz = m.group(1).strip()

    return rarity, clazz


def main():
    # === JSON 読み込み ===
    with DATA_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # === バックアップ作成（上書き防止） ===
    if not BACKUP_FILE.exists():
        with BACKUP_FILE.open("w", encoding="utf-8") as bf:
            json.dump(data, bf, ensure_ascii=False, indent=2)
        print(f"[INFO] バックアップを作成しました: {BACKUP_FILE}")
    else:
        print(f"[INFO] 既にバックアップがあります: {BACKUP_FILE}")

    updated_count = 0
    skipped_count = 0

    # === 各恐竜について Rarity / Class を取得 ===
    for slug, creature in data.items():
        url = creature.get("url")
        if not url:
            print(f"[INFO] slug={slug} : url がないためスキップします。")
            skipped_count += 1
            continue

        print(f"[GET] {url}")

        try:
            res = requests.get(url, headers=HEADERS, timeout=15)
            res.raise_for_status()
        except Exception as e:
            print(f"[WARN] {slug}: ページ取得に失敗しました: {e}")
            skipped_count += 1
            continue

        rarity, clazz = extract_classification(res.text)

        if not rarity and not clazz:
            print(f"[INFO] {slug}: Rarity / Class を抽出できませんでした。スキップします。")
            skipped_count += 1
            continue

        if "classification" not in creature or not isinstance(creature["classification"], dict):
            creature["classification"] = {}

        if rarity:
            creature["classification"]["rarity"] = rarity
        if clazz:
            creature["classification"]["class"] = clazz

        updated_count += 1
        # アクセス負荷を下げるため少し待つ
        time.sleep(0.5)

    # === JSON を上書き保存 ===
    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("=== 更新結果 ===")
    print(f"  更新した恐竜数: {updated_count}")
    print(f"  スキップした恐竜数: {skipped_count}")
    print(f"  更新ファイル: {DATA_FILE}")


if __name__ == "__main__":
    main()
