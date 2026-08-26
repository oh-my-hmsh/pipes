#!/usr/bin/env python3
"""棚に置いた実体そのものについて、**2 本のスクリプトが同じ答えを出すための 1 箇所**。

`build-catalog.py`（配る一覧を焼く）と `check-artifacts.py`（配る手前で数える）は、
どちらも「宣言した面の実体はどこに在るか」と「その実体は何版か」を知る必要が在る。

🚨 **写すと必ず片方だけ直る。** このワークスペースは同じ形を何度も踏んでいて、
直近では `handoff-toc.py` が 3 リポに割れ、**同日入れた修正が伝播していなかった**
（2026-08-17 に `agent-guidelines/tools/` へ 1 本化）。∴ ここは最初から 1 本にする。

⚠️ **実行しない。** 版は**バイナリの中の文字列を読んで**取る —— CI の台は
macOS の実体も Windows の実体も走らせられないので、走らせて訊く道は最初から無い。
"""
import pathlib
import re

# ⭐ `build-info` クレートが埋める形（`flux-tools/build-info/src/lib.rs`）。
#      "0.1.0 (a95ceb4b9)"           普通
#      "0.1.0 (a95ceb4b9-dirty)"     焼いた時に作業ツリーが汚れていた
#      "0.1.0 (a95ceb4b9-unknown)"   git status が答えなかった
#      "0.1.0 (unknown)"             git が全く答えなかった
#
# 🚨 `[0-9a-f]{9}` で固定しないこと —— 上の 3 つ目・4 つ目を**取りこぼして
#    「版が分からない」に落とす**。⭐ 「汚れた物を配ってしまった」は、まさに
#    見えていてほしい事実なので、綴りを狭めた分だけ見えなくなる。
_STAMP = re.compile(rb"\d+\.\d+\.\d+ \((?:[0-9a-f]{7,40}(?:-dirty|-unknown)?|unknown)\)")


# ⚠️ pipe の候補ではない物。`.` 始まりは `.git` 等、`__pycache__` は
# **このモジュールを import した副作用**で生まれる（＝棚の中身ではない）。
_NOT_A_PIPE = {"__pycache__"}


def pipe_dirs(root: pathlib.Path):
    """棚に並んでいる pipe のディレクトリ。⭐ **投稿の単位はディレクトリ 1 つ**。

    ⚠️ ここで飛ばすのは「pipe の候補ですらない物」だけ。`pipe.json` が無いディレクトリは
    **飛ばさずに返す** —— それは投稿し忘れかもしれないので、呼び手が**名乗って**落とす。
    """
    return sorted(p for p in root.iterdir()
                  if p.is_dir() and not p.name.startswith(".") and p.name not in _NOT_A_PIPE)


def artifact_path(pipe_dir: pathlib.Path, platform: str, bin_name: str) -> pathlib.Path:
    """宣言した面の実体が在るべき場所。⚠️ `.exe` は Windows の面だけ。"""
    name = f"{bin_name}.exe" if platform.startswith("windows") else bin_name
    return pipe_dir / platform / name


def manifest_digest(raw: bytes) -> str:
    """`pipe.json` の指紋。⭐ **バイト列そのものを見る**（正規化しない）。

    🚨 用事は「配っている宣言と、置かれた宣言は同じ物か」であって、
    「意味が同じか」ではない。⚠️ 正規化を挟むと、その規則が 2 実装に分かれた瞬間に
    **同じ宣言が違う指紋になる** —— そして誰も気づけない。

    ⭐ 暗号用途ではない（改竄ではなく**行き違い**を見る）。∴ FNV-1a 64bit で足りる。
    ⚠️ **flux 側（`registry.rs::manifest_digest`）と同じ計算**でなければ意味を成さない
    —— 🚨 ここが 2 箇所に在るのは避けられない（言語が違う）ので、
    **突き合わせる検体が両側に要る**。
    """
    # 🚨 **16 桁に揃えて書く。** flux 側で最初 `0x1000_0000_01b3` と**ゼロを 1 つ多く**
    # 書いており、⚠️ **下位 32bit は一致したまま**だったので目では気づかなかった。
    # 捕まえたのは `check-digest-agreement.py`（両側を突き合わせる検体）だけ。
    basis = 0xCBF2_9CE4_8422_2325
    prime = 0x0000_0100_0000_01B3
    mask = 0xFFFF_FFFF_FFFF_FFFF
    h = basis
    for b in raw:
        h ^= b
        h = (h * prime) & mask
    return f"{h:016x}"


# ⭐ 公開されている FNV-1a 64bit のテストベクタ。🚨 **両側の実装をここに釘付けにする** ——
# 「相手と一致していればよい」だと、**2 実装が同じように間違ったとき**に気づけない。
FNV1A_64_VECTORS = {
    "": "cbf29ce484222325",
    "a": "af63dc4c8601ec8c",
    "foobar": "85944171f73967e8",
}


def build_id_of(path: pathlib.Path) -> tuple[str | None, str]:
    """実体に埋まっている build id を返す。`(id, なぜ)` —— **id が None なら理由が入る**。

    🚨 **`None` を「持っていない」と読まないこと。** 「読めなかった」「複数あって
    決められなかった」も `None` で、⭐ そのどれなのかは 2 つ目の値だけが持っている。
    このリポは「違反が無い」と「測っていない」を混ぜる形を繰り返し踏んでいる。

    ⭐ ELF に依存しない —— 埋まっているのはただの文字列なので、**ELF / PE / Mach-O
    のどれでも同じ正規表現で当たる**（3 面 21 本で実測・2026-08-26）。
    """
    try:
        b = path.read_bytes()
    except OSError as e:
        return None, f"読めなかった: {e}"

    # ⚠️ `set` を通すのは、同じ文字列が 2 度埋まっている場合を**違いとして数えない**ため。
    # 🚨 逆に**別の値が 2 つ**在ったら、どちらを配ったかは実体からは決められない。
    found = sorted({m.decode("ascii") for m in _STAMP.findall(b)})
    if not found:
        return None, "版を名乗る文字列が埋まっていない（Rust 製でない?）"
    if len(found) > 1:
        return None, f"版が {len(found)} 通り埋まっている（決められない）: {', '.join(found)}"

    # "0.1.0 (a95ceb4b9)" → "a95ceb4b9"
    return found[0].split("(", 1)[1].rstrip(")"), ""
