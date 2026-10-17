# Security Policy

## What this tool does with your data

- **No telemetry.** This project sends nothing to analytics or tracking.
- **Network where the job requires it.** Maintainer scripts such as
  `refresh_devkit_refs.py` and `reconcile_registry.py` contact GitHub and
  PyPI to fetch upstream references, and `weekly_repo_report.py` fetches
  GitHub data and can email the report through SMTP — that is their
  documented purpose. Everything else runs locally.
- **Data stays on your machine** apart from the fetches above.

## Sensitive data handling

- Output intended for sharing must pass through
  [`devin-redact`](https://github.com/Icaro0310/devin-state) before publication.
- Never commit Devin session databases, `.env` files, tokens, or pairing codes.

## Verifying release signatures

GitHub release wheels, sdists and `sbom.cdx.json` across the ecosystem
carry detached GPG signatures (`*.asc`). Verify any artifact with the
public key published on the maintainer's GitHub profile:

```sh
curl -sL https://github.com/Icaro0310.gpg | gpg --import
gpg --verify <artifact>.asc <artifact>
```

Expected fingerprint:
`E224 176E E96D 21B2 F8D4 AD5D B947 5711 795E 531E`

Scope and limits: `*.asc` files sign the Python distributions and the
SBOM only — the packaged `.vsix` extension is currently unsigned, and
PyPI itself carries no signature (verify against the GitHub release
asset of the same name, not the PyPI file). The SBOM signature attests
the manifest's integrity; it is not a build attestation.

## Reporting a vulnerability

Open a **private** security advisory on GitHub, or open an issue marked
`[SECURITY]` **without** including the vulnerable data itself.

Do not file public issues containing secrets, tokens, or session content.
