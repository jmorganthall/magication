# Releasing

`magication-moat` publishes to PyPI automatically on every push to `main`
via `.github/workflows/publish.yml`.

## How it works
- **Versioning** is derived from git by `setuptools-scm` — no manual version bumps.
  Each commit on `main` produces a unique, PyPI-safe version (e.g. `0.0.1.devN`),
  so re-publishing never collides. Cut a real release by tagging: `git tag v0.1.0 && git push --tags`.
- **Publishing** uses PyPI **trusted publishing** (OIDC) — there is no API token stored
  in GitHub Secrets.

## One-time setup (required before the first publish succeeds)
The publish step will fail until the PyPI side is configured:

1. Create the project on PyPI (or reserve the name `magication-moat`).
2. In the PyPI project's **Publishing** settings, add a **GitHub Actions trusted publisher**:
   - Owner: `jmorganthall`
   - Repository: `magication`
   - Workflow filename: `publish.yml`
   - Environment name: `pypi`
3. In this GitHub repo, create an **Environment** named `pypi`
   (Settings → Environments) — optionally add required reviewers to gate releases.

## Switching targets
- **TestPyPI instead:** add `repository-url: https://test.pypi.org/legacy/` under the
  `pypa/gh-action-pypi-publish` step, and register the trusted publisher on TestPyPI.
- **Only release on tags:** change the workflow trigger to `on: push: tags: ['v*']`.
