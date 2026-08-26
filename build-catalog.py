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

from flux_artifacts import artifact_path, build_id_of, manifest_digest, pipe_dirs

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


def build_ids_of(pipe_dir: pathlib.Path, meta: dict) -> dict[str, str]:
    """宣言した面それぞれの build id を、**実体から読んで**返す。

    🚨 **`pipe.json` に手で書く欄にしない。** そうすると同じ事実が 2 箇所に在ることになり、
    焼き直した回に片方だけ動いて必ず腐る —— そして腐った側は「最新です」と言い続ける。
    ⭐ ここが**導出**である限り、カタログは焼き直した瞬間に正しくなる。

    ⚠️ 版が読めない面は**欄ごと落とす**（`PASSTHROUGH` と同じ作法 ——
    「持っていない」と「空」を同じ顔にしない）。python の pipe はそもそも
    `platforms` を名乗らないのでここに来ない。

    ⭐ **揃っているかは判定しない。** 面ごとに違うのは正常なことも事故なこともあり、
    その区別は `check-artifacts.py` の仕事（あちらは git を見られる）。ここは**運ぶだけ**。
    """
    platforms = meta.get("platforms")
    bin_name = meta.get("bin_name")
    if not platforms or not bin_name:
        return {}
    out = {}
    for platform in platforms:
        build_id, why = build_id_of(artifact_path(pipe_dir, platform, bin_name))
        if build_id is None:
            print(f"  ・ {pipe_dir.name} {platform}: 版を載せません（{why}）", file=sys.stderr)
            continue
        out[platform] = build_id
    return out


def build() -> dict:
    pipes = []
    for d in pipe_dirs(ROOT):
        manifest = d / "pipe.json"
        if not manifest.is_file():
            print(f"  skip {d.name}/ (pipe.json 無し)", file=sys.stderr)
            continue
        raw = manifest.read_bytes()
        meta = json.loads(raw.decode("utf-8"))
        entry = {"id": d.name}
        entry.update({k: meta[k] for k in PASSTHROUGH if k in meta})
        # ⭐ **唯一、pipe.json ではなく実体から来る欄。** 利用者の `flux outdated` が
        # 「いま入っている物は配っている物と同じか」に答えるための正本。
        build_ids = build_ids_of(d, meta)
        if build_ids:
            entry["build_ids"] = build_ids
        # ⭐ **2 本目の軸。** バイナリの版（`build_ids`）とは別に、**宣言そのもの**の指紋。
        # 🚨 宣言だけが変わる回は普通に在る —— 実測で、`.manifests/` を触った直近
        # 6 コミットのうち **4 回**がバイナリを 1 行も動かしていなかった。
        # ⚠️ そのとき `build_ids` は動かないので、片方だけ見ていると
        # **「最新です」と言いながら古い宣言を配られたまま**になる（flux-tools #12）。
        entry["manifest_digest"] = manifest_digest(raw)
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
