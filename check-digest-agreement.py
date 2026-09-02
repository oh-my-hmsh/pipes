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


def _host_platforms() -> tuple[str, ...]:
    """この台で **exec できる見込みの在る** 面を、試す順に返す。

    🚨 **`os.access(X_OK)` は面を見ない。** ELF にも実行ビットは立っているので、
    macOS では「在る・実行できる」と答えたあとで `exec` が落ちる。
    ∴ 権限ではなく**面**で先に絞る。

    ⚠️ ここが空になる台（未知の OS / arch）は「測れない」と名乗って落ちる ——
    ⭐ 知らない台で*たまたま*動く物を探しに行くより、名乗る方が安い。
    """
    import platform

    system, machine = platform.system(), platform.machine()
    if system == "Linux" and machine in ("x86_64", "AMD64"):
        return ("linux-x86_64",)
    if system == "Darwin" and machine == "arm64":
        return ("macos-aarch64",)
    if system == "Windows" and machine in ("x86_64", "AMD64"):
        return ("windows-x86_64",)
    return ()


_PLATFORM_ORDER = _host_platforms()


def _runnable_flux() -> str | None:
    """リポの中の `flux` を、**この台の面**から選ぶ。無ければ PATH に落ちる。

    ⭐ 実際に `--version` を撃って**走ることまで**確かめる —— 📏 ファイルが在って
    実行ビットが立っているのに `exec` が落ちる、が現に起きた形なので、
    「在る」で満足しない。
    """
    for platform_dir in _PLATFORM_ORDER:
        cand = ROOT / "flux" / platform_dir / ("flux.exe" if platform_dir.startswith("windows") else "flux")
        if not (cand.is_file() and os.access(cand, os.X_OK)):
            continue
        try:
            r = subprocess.run([str(cand), "--version"], capture_output=True, timeout=10)
        except OSError:
            continue  # 🚨 面が違う（Exec format error）—— ここで握るのが目的
        if r.returncode == 0:
            return str(cand)
    return shutil.which("flux")


def main() -> int:
    # ⭐ **配ろうとしている実体そのもの**を使う（棚に在る物ではなく）——
    # 検査したいのは「この回に publish される flux が、この回のカタログと一致するか」。
    # ⚠️ CI には flux が入っていないが、**リポの中に在る**ので依存は増えない。
    #
    # 🚨 **ただし「この台で走る面」を選ぶこと**（2026-09-02・m4air で踏んだ）。
    # 長く `flux/linux-x86_64/flux` を決め打ちしていた。⭐ CI（linux）では当たるが、
    # 📏 macOS から撃つと `OSError: Exec format error` の**生の traceback** で落ちる ——
    # 🚨 「指紋が食い違った」ではなく「**ここでは測れない**」なのに、そう読めない形で。
    # ⚠️ このリポの `check-artifacts.py` は自分の doc で「測らなかったときに緑を返さない」と
    # 書いているが、こちらは**その裏面**（測れなかったときに、測って落ちた顔をする）を踏んでいた。
    #
    # ⭐⭐ 面は**どれでもよい** —— 見たいのは指紋の計算が python と rust で一致するかで、
    # それは面に依らない。∴ **走る物を選ぶ**のが正しく、linux に固執する理由は無い。
    flux = _runnable_flux()
    if not flux:
        print("flux を**この台で走る形では**見つけられません"
              f"（試した面: {', '.join(_PLATFORM_ORDER)} ／ PATH）——\n"
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
