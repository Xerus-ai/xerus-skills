# Verifying code blocks against real APIs

Upstream skills are snapshots. Months later, their code blocks use exports that were removed,
signatures that changed at a major version, and defaults that flipped. Refreshing version numbers
does not catch any of this. Checking a package manager's "latest version" tells you the number,
not the API. In one real batch, writers bumped every pin and still shipped removed exports,
changed signatures and a JWT check that accepted forged tokens. What caught them was unpacking the
published package and reading its type declarations.

**Rule:** before a writer reports, every code block in a typed ecosystem has been type-checked in
strict mode against the real published package at the version the skill names. Hand writers the
unpacked typings up front. Do not leave them to discover the rule after a verifier REJECT.

## Procedure (any ecosystem)

1. **Pin**: take the version the skill states (after refreshing it to current).
2. **Fetch the real artifact** into a scratch folder you own: the published package, not the repo's
   main branch.
3. **Read the declarations** for every import the block uses: does the export exist, what is its
   signature, what are its defaults?
4. **Extract** each code block into a file in a scratch project, with the minimum glue needed
   (declared environment types, stub values). Do not change the block's logic to make it compile.
   If it needs changing, the skill needs changing.
5. **Type-check strictly.** Fix the skill until clean. Record the command and result in your report.
6. **Clean up** the scratch folder by exact path when done (or leave it for the verifier if asked).

## TypeScript / JavaScript (npm)

```bash
mkdir -p work/batch-NNN/tc && cd work/batch-NNN/tc
npm view some-package version          # the NUMBER only; still do the next steps
npm pack some-package@1.4.2            # downloads the published tarball
tar -xzf some-package-1.4.2.tgz        # unpacks into package/
grep -rn "export declare function createHandler" package/dist/*.d.ts
```

For a type-check project: `npm init -y`, `npm install typescript some-package@1.4.2` plus any
`@types/*` or platform type packages the code uses, then a `tsconfig.json` with at least
`"strict": true, "noEmit": true, "skipLibCheck": true` and the module/target settings the platform
needs. Put each block in `blocks/<skill>-<n>.ts` and run `npx tsc -p .`.

Plain-JS blocks: check with `// @ts-check` and `"allowJs": true, "checkJs": true`.

## Python

```bash
python -m venv work/batch-NNN/venv
work/batch-NNN/venv/bin/pip install "some-package==2.3.0" mypy   # Scripts\ on Windows
work/batch-NNN/venv/bin/python -c "import inspect, some_package as m; print(inspect.signature(m.connect))"
work/batch-NNN/venv/bin/mypy --strict blocks/
```

For untyped libraries, `inspect.signature` and a real import (`python -c "from pkg import name"`)
are the minimum. An import that fails is a removed export.

## Other ecosystems

| Ecosystem | Fetch | Check |
|---|---|---|
| Go | a module with `go get pkg@vX.Y.Z` | `go vet ./...` and `go build ./...` |
| Rust | a crate with the version in `Cargo.toml` | `cargo check` |
| Java/Kotlin | the dependency at the version | compile with the build tool |
| Shell/CLI | install the real CLI version | run `<cli> <subcommand> --help`, confirm every flag used exists |
| HTTP APIs | the vendor's API reference or OpenAPI spec | endpoints, params and auth scheme match the reference; mark "verify" if you cannot call it |

## What type-checking does not prove

It proves the code matches the published API surface. It does not prove the code works against a
live service, has correct runtime semantics, or is secure. Report it honestly: "type-checked
against pkg@1.4.2 declarations" is a different claim from "ran against a live account". Security
logic (who can forge what) needs a human-level read even when it compiles.
