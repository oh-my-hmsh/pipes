#!/usr/bin/env python3
"""🚨 **指紋の計算が、配る側と入れる側で一致しているか。**

`manifest_digest` は **2 つの実装に分かれている**（配る側は Python、入れる側は Rust）。
⚠️ 言語が違うので 1 本化できない —— ⭐ **∴ 突き合わせる検体でしか守れない。**

食い違うと何が起きるか: **配っている宣言と手元の宣言が同じでも、指紋が違う**
→ `flux outdated` が**全部を「宣言が古い」と言い続ける**（そして入れ直しても直らない）。
🚨 黙って壊れる形で、しかも**入れ直しが効かない**ので、原因に辿り着くのが難しい。

    ./check-digest-agreement.py            食い違えば非ゼロ

⚠️ flux が手元に無ければ**測れない**と名乗って落ちる（緑にしない）。
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys

from flux_artifacts import FNV1A_64_VECTORS, manifest_digest, pipe_dirs

ROOT = pathlib.Path(__file__).parent


def main() -> int:
    # ⭐ **配ろうとしている実体そのもの**を使う（棚に在る物ではなく）——
    # 検査したいのは「この回に publish される flux が、この回のカタログと一致するか」。
    # ⚠️ CI には flux が入っていないが、**リポの中に在る**ので依存は増えない。
    here = ROOT / "flux" / "linux-x86_64" / "flux"
    flux = str(here) if here.is_file() and os.access(here, os.X_OK) else shutil.which("flux")
    if not flux:
        print("flux が見つかりません（リポの flux/linux-x86_64/flux も PATH も）——\n"
              "一致するのではなく、**測れていません**。", file=sys.stderr)
        return 1
    print(f"  使う flux: {flux}")

    # 🚨 **まず両側を公開ベクタに突き合わせる。** 「相手と一致していればよい」だと、
    # **2 実装が同じように間違ったとき**に気づけない（実際、素数を 1 桁多く書いて
    # 下位 32bit だけ一致する、という形を踏んだ）。
    import tempfile
    for text, want in FNV1A_64_VECTORS.items():
        mine = manifest_digest(text.encode())
        with tempfile.NamedTemporaryFile("wb", delete=False, suffix=".json") as f:
            f.write(text.encode())
            tmp = f.name
        theirs = subprocess.run([flux, "digest", tmp], capture_output=True, text=True).stdout.strip()
        pathlib.Path(tmp).unlink(missing_ok=True)
        if mine != want or theirs != want:
            print(f"🔴 FNV-1a の既知の値と違います（{text!r}）: "
                  f"python={mine} rust={theirs} 期待={want}", file=sys.stderr)
            return 1
    print(f"✅ 両側とも FNV-1a の既知の値 {len(FNV1A_64_VECTORS)} 件と一致")

    # ⭐ Rust 側の答えは `flux` に出させる（隠しコマンド。人向けの面ではない）。
    checked = 0
    bad: list[str] = []
    for d in pipe_dirs(ROOT):
        m = d / "pipe.json"
        if not m.is_file():
            continue
        raw = m.read_bytes()
        mine = manifest_digest(raw)
        r = subprocess.run([flux, "digest", str(m)], capture_output=True, text=True)
        if r.returncode != 0:
            bad.append(f"{d.name}: flux が答えませんでした（{r.stderr.strip()[:80]}）")
            continue
        theirs = r.stdout.strip()
        checked += 1
        if mine != theirs:
            bad.append(f"{d.name}: python={mine} rust={theirs}")

    # 🚨 母集団が空なら「一致」ではなく「測っていない」。
    if checked == 0:
        print("\n1 本も突き合わせられませんでした。一致したのではありません。", file=sys.stderr)
        return 1
    if bad:
        print(f"\n{len(bad)} 件:", file=sys.stderr)
        for b in bad:
            print(f"  🔴 {b}", file=sys.stderr)
        return 1
    print(f"✅ 指紋の計算は {checked} 本とも一致しています（python ↔ rust）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
