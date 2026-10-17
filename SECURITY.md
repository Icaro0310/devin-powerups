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
curl -sL https://github.com/Icaro0310.gpg -o icaro0310.asc
gpg --show-keys --with-colons icaro0310.asc | awk -F: '/^fpr/ {print $10; exit}'
# must print exactly: E224176EE96D21B2F8D4AD5DB9475711795E531E — abort if it does not

# verify inside an isolated keyring that holds only this key: in your own
# keyring `gpg --verify` succeeds for ANY trusted signer, so a substituted
# artifact signed by another key you hold would also pass.
export GNUPGHOME="$(mktemp -d)"
gpg --import icaro0310.asc
gpg --verify <artifact>.asc <artifact>
rm -rf "$GNUPGHOME"; unset GNUPGHOME
```

Both checks are mandatory: importing whatever key the profile serves and
calling `gpg --verify` would accept artifacts signed by any key placed
there, and verifying in a shared keyring would accept artifacts signed by
any key already trusted there. The signature is only trustworthy if the
key's fingerprint matches `E224 176E E96D 21B2 F8D4 AD5D B947 5711 795E
531E` exactly and the keyring holds no other keys.

Scope and limits: `*.asc` files sign the Python distributions and the
SBOM only — the packaged `.vsix` extension is currently unsigned. PyPI
itself carries no signatures; to authenticate a PyPI download, fetch the
same-named asset from the GitHub release, verify its `.asc`, then compare
`sha256sum` digests of the PyPI file and the verified GitHub asset —
matching filenames alone prove nothing about the bytes. The SBOM
signature attests the manifest's integrity; it is not a build attestation.

## Reporting a vulnerability

Open a **private** security advisory on GitHub, or open an issue marked
`[SECURITY]` **without** including the vulnerable data itself.

Do not file public issues containing secrets, tokens, or session content.
