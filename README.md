# 🔧 Oh My hmsh — Pipes

Community pipes for [**hmsh**](https://hsh.navii.online), the Hermes shell.

All pipes follow the **Flux Protocol v1** — they read and/or write NDJSON on stdin/stdout, making them composable with each other and standard Unix tools.

## Installation

```bash
hmsh pipe install flux-render
hmsh pipe install filter-json
```

Or install directly from a repository:

```bash
hmsh pipe install oh-my-hmsh/pipes
```

`hmsh pipe list` shows what you have installed.

> Pipes belong to **hmsh**, not to `hsh`. `hsh` is the POSIX/bash-compatible
> shell and deliberately ships without a package manager — there is no
> `hsh pipe` command; on that side a pipe is just a binary on your `PATH`.
> `hm` and `hsh-hermes` also work; they are aliases for `hmsh`.

## Available Pipes

| Pipe | Description | Runtime |
|------|-------------|---------|
| [flux-eye](./flux-eye/) | High-speed filesystem scanner | Binary |
| [flux-grep](./flux-grep/) | Fast signal extraction from NDJSON streams | Binary |
| [flux-render](./flux-render/) | Universal format converter (NDJSON ↔ Markdown/CSV/YAML) | Python 3 |
| [filter-json](./filter-json/) | Filter NDJSON streams by keyword | Python 3 |
| [json-to-table](./json-to-table/) | Render NDJSON as ASCII tables | Python 3 |

## Writing Your Own Pipe

Any executable that reads/writes NDJSON can be a Flux pipe. Here's a minimal example in Python:

```python
#!/usr/bin/env python3
import json, sys
for line in sys.stdin:
    record = json.loads(line)
    record["processed"] = True
    print(json.dumps(record), flush=True)
```

Save it, `chmod +x`, and pipe it: `flux-eye -p . | ./my-pipe`

**To get it listed here**, fork this repository, add `<your-pipe>/` with a `pipe.json`
manifest, and open a pull request — that directory is the whole change. `pipes.json` is
**generated** from the manifests by `./build-catalog.py`, so there is nothing else to update.
CI rejects a hand-edited catalog.

**Shipping a compiled pipe?** Declare the faces you baked in `platforms`, and put each
binary at `<id>/<platform>/<bin_name>`. CI runs `./check-artifacts.py`, which requires
that every declared face actually has a binary, and that the `linux-x86_64` one is
**statically linked** — a dynamically linked binary will not start on a glibc older than
the one it was built against, which is not a failure the person installing it can diagnose.
Build it with `--target x86_64-unknown-linux-musl`; that flag looks redundant when you are
sitting at a Linux machine, and that is exactly when it goes missing. Run the script
yourself before you publish.

**Prefer to keep it in your own repository?** You do not need to be listed:

```bash
hmsh pipe install <user>/<repo>
```

## License

MIT
