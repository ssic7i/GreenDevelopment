# Publish GreenDevelopment on GitHub

The local repository is prepared on `main` with an initial commit. No GitHub repository or remote is configured by this preparation. The plugin ID is `green-development`; the suggested GitHub repository name is `GreenDevelopment`.

## First publication

Create an empty repository on GitHub under your account/organization. Keep the local README, license and Git history as the initial content. Then, from this repository root, replace `OWNER` with the real owner:

```sh
git status --short
git remote add origin https://github.com/OWNER/GreenDevelopment.git
git push -u origin main
```

Alternatively, with GitHub CLI installed and authenticated:

```sh
gh repo create OWNER/GreenDevelopment --public --source=. --remote=origin --push
```

Choose one route. These commands publish the repository; run them when ready. Keep it private instead if public release is not intended.

After publication, replace `OWNER/GreenDevelopment` placeholders in installation examples with the actual repository. The package manifest intentionally omits an unverified repository/homepage URL.

## Version release

After checks pass and release changes are committed:

```sh
git tag -a v0.3.3 -m "GreenDevelopment 0.3.3"
git push origin v0.3.3
git archive --format=zip --prefix=GreenDevelopment/ \
  --output=../GreenDevelopment-source.zip v0.3.3
```

Create a GitHub release from the tag and attach the verified source ZIP and optional plugin ZIP. GitHub's generated source archive also retains the repository installation catalog. The initial prepared plugin ZIP excludes marketplace/Git/CI metadata and is a different artifact from the source ZIP.

Review the GitHub Actions result after pushing. Hosted CI has not run merely because local tests passed. For release notes use the tested behavior and limitations from [VALIDATION.md](../VALIDATION.md).

GitHub publication and Codex marketplace installation are separate from submission to OpenAI's public plugin directory; this repository preparation does not submit a directory listing.

Reference: [GitHub's guide to publishing local code](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github).
