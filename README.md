# 🔧 flux — registry

Where the **flux** family is published: the catalog, the declarations, and prebuilt
binaries for each platform.

Everything here speaks **Flux Protocol v1** — NDJSON records on stdin/stdout, so the tools
compose with each other and with ordinary Unix commands.

## Installation

```bash
flux install flux-eye
flux search json
flux outdated          # is what I have still what is published?
```

`flux` itself is published here, but a package manager cannot be the thing that installs
itself the first time. Fetch it directly for your platform
(`linux-x86_64`, `macos-aarch64`, `windows-x86_64`):

```bash
curl -fsSL -o ~/.local/bin/flux \
  https://raw.githubusercontent.com/flux-tools/registry/main/flux/linux-x86_64/flux
chmod +x ~/.local/bin/flux
flux --version          # check it runs before trusting it
```

After that, `flux update flux` keeps it current.

> ⭐ **These are ordinary commands.** `flux-eye ~/project` works on a bare machine with
> no shell integration, no manifest, and no package manager — the binary on your `PATH`
> is the whole product. What `flux` adds is carrying the *declaration* beside it, which
> only matters to programs that build command lines for you.
>
> They are already used four ways: from an MCP server that spawns them by name, from a
> plain shell pipeline, from a dot-chain, and by typing them. The registry is named for
> what it is rather than for any one of those.

## Available Pipes

| Pipe | Description | Runtime |
|------|-------------|---------|
| [flux](./flux/) | The package manager itself | Binary |
| [flux-eye](./flux-eye/) | High-speed filesystem scanner | Binary |
| [flux-find](./flux-find/) | Fuzzy filename search | Binary |
| [flux-grep](./flux-grep/) | Fast signal extraction from NDJSON streams | Binary |
| [flux-priority](./flux-priority/) | Rank files by relevance | Binary |
| [flux-read](./flux-read/) | Token-budgeted file reader | Binary |
| [flux-write](./flux-write/) | Write, move, mkdir | Binary |
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

Save it, `chmod +x`, and pipe it: `flux-eye . | ./my-pipe`

**To get it listed here**, fork this repository, add `<your-pipe>/` with a `pipe.json`
manifest, and open a pull request — that directory is the whole change. `pipes.json` is
**generated** from the manifests by `./build-catalog.py`, so there is nothing else to update.
CI rejects a hand-edited catalog.

CI also checks that every published binary **announces its own build id** (`--version`
prints `<semver> (<build id>)`), because that is what tells an installed copy whether it
is still the one being published. A binary that cannot say which build it is turns
"is this current?" into "cannot tell" on every machine that installs it, and only the
publisher can fix that.

**Shipping a compiled pipe?** Declare the faces you baked in `platforms`, and put each
binary at `<id>/<platform>/<bin_name>`. CI runs `./check-artifacts.py`, which requires
that every declared face actually has a binary, and that the `linux-x86_64` one is
**statically linked** — a dynamically linked binary will not start on a glibc older than
the one it was built against, which is not a failure the person installing it can diagnose.
Build it with `--target x86_64-unknown-linux-musl`; that flag looks redundant when you are
sitting at a Linux machine, and that is exactly when it goes missing. Run the script
yourself before you publish.

**Prefer to keep it in your own repository?** You do not need to be listed at all —
drop the binary on your `PATH` and type its name. Being in this registry buys you two
things: other people can find it, and the declaration travels with it.

**Working on one locally?** `flux install --from <repo>` installs from a checkout that has
a `.manifests/` directory, so you can try a tool before publishing anything.

## License

MIT
