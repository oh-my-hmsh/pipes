#!/usr/bin/env python3
"""配る前に、**宣言した面の実体が在るか**と **linux 面が静的か**を数える。

    ./check-artifacts.py            数えて表で出す（違反が在れば非ゼロ）

# 🚨 なぜ機械が守るのか —— 2026-08-26 に、動的リンクの物を配っていた

`flux-eye/linux-x86_64/flux-eye` が glibc に動的リンクされたまま publish されていた。
⭐ musl 静的を選んだ理由は「**古い glibc の利用者では起動しない**」なので、
配っている物がその決定を満たしていなかった。

## ⭐ 原因は「flux-eye だから」ではない —— **`--target` が「よその面」の合図に見える**

`target/` の mtime が残していた:

    08-25 14:46  他 5 本 × musl と windows-gnu を続けて焼いた   → --target が両方に在る
    08-26 03:10  flux-eye の release/（ネイティブ）              → --target が無い  ← これが配られた
    08-26 03:37  flux-eye の x86_64-pc-windows-gnu              → --target が在る

⭐ 同じ回の中で、**よその面には付け、座っている台と同じ面には付けなかった**。
`--target` は「クロスコンパイルの旗」に見えるので、ネイティブ面では冗長に見える ——
⚠️ ところが musl は**同じ面の中での選択**なので、そこでこそ要る。
🚨 ∴ **どの道具でも、publish の回の外で単独に焼き直せば同じことが起きる**
（08-25 に 5 本が助かったのは windows と続けて焼いた回だったから ＝ 運）。

⭐ **注意では直らない形**なので、配る手前で数える。

# ⚠️ 静的かどうかを **`ldd` でも `file` でも判定しない**

どちらも**言葉で答える道具**で、綴りが違う:

    $ ldd  flux-find     → statically linked
    $ file flux-find     → ... , static-pie linked, ...     ← 別の言い方

🚨 2026-08-26 に実際に踏んだ —— `file` の出力から `statically linked` を探して、
**6 本中 5 本が「判定不能」で無言**になった（赤が 1 本だけ在るように見えた）。
⭐ 片方の語彙で grep すると、**違反ではなく計測不能が黙って混ざる**。

∴ ここは **ELF のプログラムヘッダを直接読み、`PT_INTERP` の有無で決める**。
それが `ldd` の言う「動的」の実体（＝起動時にどのローダーを呼ぶかの宣言）で、
言い回しに依存せず、**成果物を実行せずに**、CI の台の loader も要らずに読める。

# 🚨 何も測らなかったときに緑を返さない

母集団が空なら違反も 0 件になる —— この repo が何度も踏んでいる形。
∴ **数えた実体が 0 個なら非ゼロで終わる**。「違反なし」と「測っていない」は別の事実。

# ⭐ 宣言駆動 —— 当てにいかない

何を見るかは `<id>/pipe.json` の **`platforms`** が決める（`build-catalog.py` と同じ根拠）。
`platforms` が無い pipe は台に依らない物（python 等）なので、**見ない**と名乗って飛ばす。
⚠️ 逆に、**宣言した面の実体が無ければ違反**。宣言と棚が食い違うと、利用者には
「その pipe は無い」と「あなたの台の分は焼いていない」が**同じ 404** に化ける。
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent

PT_INTERP = 3
# 静的を要求する面。⚠️ musl は **Linux での規約**なので、他の面はここに載せない
# （macOS / Windows は事情が違い、同じ物差しを当てると偽の赤になる）。
MUST_BE_STATIC = {"linux-x86_64"}


def artifact_path(pipe_dir: pathlib.Path, platform: str, bin_name: str) -> pathlib.Path:
    """宣言した面の実体が在るべき場所。⚠️ `.exe` は Windows の面だけ。"""
    name = f"{bin_name}.exe" if platform.startswith("windows") else bin_name
    return pipe_dir / platform / name


def has_interp(path: pathlib.Path) -> bool | None:
    """ELF が `PT_INTERP` を持つか。⭐ 持つ ＝ 動的リンク。ELF でなければ `None`。

    ⚠️ **`None` は「動的でない」ではなく「読めなかった」** —— 呼び手はこれを緑に
    畳まないこと（静的 PIE は `ET_DYN` だが `PT_INTERP` を持たない、という違いを
    潰してしまう）。
    """
    b = path.read_bytes()
    if len(b) < 64 or b[:4] != b"\x7fELF":
        return None
    is64 = b[4] == 2
    endian = "little" if b[5] == 1 else "big"

    def num(off: int, size: int) -> int:
        return int.from_bytes(b[off:off + size], endian)

    phoff = num(0x20, 8) if is64 else num(0x1C, 4)
    phentsize = num(0x36, 2) if is64 else num(0x2A, 2)
    phnum = num(0x38, 2) if is64 else num(0x2C, 2)
    if phoff == 0 or phentsize == 0 or phnum == 0:
        return None
    for i in range(phnum):
        off = phoff + i * phentsize
        if off + 4 > len(b):
            return None
        if num(off, 4) == PT_INTERP:
            return True
    return False


def main() -> int:
    examined = 0          # 実際に中を読んだ実体の数（🚨 0 なら緑にしない）
    problems: list[str] = []
    skipped: list[str] = []
    rows: list[tuple[str, str, str]] = []

    for d in sorted(p for p in ROOT.iterdir() if p.is_dir() and not p.name.startswith(".")):
        manifest = d / "pipe.json"
        if not manifest.is_file():
            skipped.append(f"{d.name}/ (pipe.json 無し)")
            continue
        meta = json.loads(manifest.read_text(encoding="utf-8"))
        platforms = meta.get("platforms")
        if not platforms:
            skipped.append(f"{d.name} (platforms を名乗らない ＝ 台に依らない物)")
            continue
        bin_name = meta.get("bin_name")
        if not bin_name:
            problems.append(f"{d.name}: platforms が在るのに bin_name が無い（住所が組めない）")
            continue

        for platform in platforms:
            path = artifact_path(d, platform, bin_name)
            rel = str(path.relative_to(ROOT))
            if not path.is_file():
                problems.append(f"{rel}: 宣言した面の実体が無い")
                rows.append((rel, "🔴", "実体が無い"))
                continue
            if platform not in MUST_BE_STATIC:
                rows.append((rel, "・", "静的を要求しない面"))
                continue
            examined += 1
            interp = has_interp(path)
            if interp is None:
                problems.append(f"{rel}: ELF として読めなかった（測れていない）")
                rows.append((rel, "🔴", "ELF として読めない"))
            elif interp:
                problems.append(
                    f"{rel}: 動的リンク（PT_INTERP 在り）。"
                    f"--target x86_64-unknown-linux-musl を付けて焼き直すこと")
                rows.append((rel, "🔴", "動的リンク"))
            else:
                rows.append((rel, "✅", "静的"))

    for rel, mark, note in rows:
        print(f"  {mark} {rel:<46} {note}")
    for s in skipped:
        print(f"  ・ 見ていない: {s}")

    # 🚨 母集団が空なら「違反なし」ではなく「測っていない」。
    if examined == 0:
        print(f"\n静的かどうかを測れた実体が 0 個でした（{'/'.join(sorted(MUST_BE_STATIC))} が 1 つも無い）。"
              f"\n違反が無いのではなく、**何も測っていません**。", file=sys.stderr)
        return 1

    if problems:
        print(f"\n{len(problems)} 件:", file=sys.stderr)
        for p in problems:
            print(f"  🔴 {p}", file=sys.stderr)
        return 1

    print(f"\n✅ 宣言した面の実体は全部在り、linux 面 {examined} 本とも静的です。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
