#!/usr/bin/env python3
"""pipes.json を pipes/<id>/pipe.json から焼く。**手で編集しない。**

🚨 なぜ生成物なのか
    手書きのカタログは、中身から離れた瞬間に腐る。2026-08-19 の実測で 3 つ出た:
      1. カタログは 8 件を載せていたが、ディレクトリは 6 個（`dracula-minimal` /
         `powerlevel` は実体なし）＝ **幽霊エントリ**
      2. 同じ `description` が実体とカタログで**別の文**だった（`pure` も `flux-eye` も）
      3. 同じカタログが `registry/` にも複製されており、org 改名が片方にしか当たっていなかった

⭐ 生成にすると、この 3 つは**構造的に起きなくなる**。投稿者の PR は自分のディレクトリ 1 つだけで、
   一覧は merge した瞬間に正しくなる。

⚠️ `repo` フィールドは**書かない**。中身はこのリポの `<id>/` に在るので、住所は id から決まる
   （以前は `oh-my-hsh/<id>` という存在しないリポを指していて、install が必ず 404 だった）。
   自分のリポで持ちたい人は `hmsh pipe install <user>/<repo>` が直接通る。
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "pipes.json"

# カタログに載せる欄。⚠️ pipe.json に無ければ**黙って省く**（空文字で埋めない
# —— 「説明が無い」と「説明が空」は別の事実）。
# ⚠️ `bin_name` はクライアントが**取得 URL の組み立てに使う**ので必須級。
#
# ⭐ `platforms` は **住所の形そのものを決める**（2026-08-25・hsh `#210` の続き）:
#      無い  → 台に依らない物（python 等）。`<id>/<bin_name>`
#      在る  → 焼き分けた物。`<id>/<platform>/<bin_name>[.exe]`
#    ∴ クライアントは分岐を持たず、**カタログが形を名乗る**。
# 🚨 これを落とすと「その pipe は無い」と「あなたの台の分は焼いていない」が**同じ 404** に
#    化ける —— 前者を見た人は存在しない物を探しに行く。**別の事実は別に言う。**
PASSTHROUGH = ["name", "version", "description", "author", "author_url", "bin_name",
               "runtime", "usage", "license", "tags", "min_hsh_version", "platforms"]


def build() -> dict:
    pipes = []
    for d in sorted(p for p in ROOT.iterdir() if p.is_dir() and not p.name.startswith(".")):
        manifest = d / "pipe.json"
        if not manifest.is_file():
            print(f"  skip {d.name}/ (pipe.json 無し)", file=sys.stderr)
            continue
        meta = json.loads(manifest.read_text(encoding="utf-8"))
        entry = {"id": d.name}
        entry.update({k: meta[k] for k in PASSTHROUGH if k in meta})
        pipes.append(entry)
    return {"version": 1, "pipes": pipes}


def main() -> int:
    built = build()
    text = json.dumps(built, ensure_ascii=False, indent=2) + "\n"
    if "--check" in sys.argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            print("pipes.json が pipes/<id>/pipe.json と食い違っています。"
                  "`./build-catalog.py` を実行してコミットしてください。", file=sys.stderr)
            return 1
        print(f"pipes.json は最新です（{len(built["pipes"])} 件）")
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"pipes.json を焼きました（{len(built["pipes"])} 件）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
