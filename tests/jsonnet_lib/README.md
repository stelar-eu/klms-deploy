# Jsonnet library tests

The repository root is intentionally not a Tanka workspace. These dependency
files exist only to test the Jsonnet deployment library from a source checkout.

Install the test dependencies into the ignored root `vendor/` directory with:

```bash
cd tests/jsonnet_lib
jb --jsonnetpkg-home ../../vendor install
cd ../..
```

Then run the Jsonnet tests from the repository root:

```bash
python -m pytest tests/jsonnet_lib
```

Operator workspaces do not use this manifest. `stelarctl workspace init` writes
the packaged dependency manifest from `src/stelar/deploy/templates/`, and
`jb install` in that workspace downloads this repository's active `lib/` tree
along with its external Jsonnet dependencies.
