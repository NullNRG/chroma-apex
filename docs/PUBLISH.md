# GitHub publication (manual, no GitHub Actions)

The GitHub connection currently available to the assistant can work inside existing repositories, but does not offer an action to create a *new* repository. We intentionally do not push these files into an unrelated repository. The supplied ZIP and git bundle are complete, stand-alone artifacts.

Once repository creation is available, use a dedicated public repository (suggested `NullNRG/chroma-apex`). To create locally using GitHub CLI **on your own computer**:

```sh
# from a checkout of this repository with existing git history
# github.com requires you to log in once: gh auth login
gh repo create chroma-apex --public --source=. --remote=origin --push
```

Alternative through GitHub website: create a new empty repo named `chroma-apex` (no README/license initialization), then:

```sh
git remote add origin https://github.com/NullNRG/chroma-apex.git
git push -u origin main
```

Verify the repository README, MIT license and tests; then tag `v0.1.0` and push the tag if you decide to release it. Do not enable GitHub Actions or paid runners by default. Publisher should review `docs/LEGAL_AND_PROVENANCE.md` before public release.
