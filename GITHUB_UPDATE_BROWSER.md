# Publish God Save Birmingham Docker v10.1.0 using only a web browser

Your existing published release is `v10.0.1` at `ghcr.io/quietudevs/gsb-wine:v10.0.1`. Keep it as a known rollback until the new image is tested.

1. Download `gsb-docker-v10.1.0-source.zip` and **Extract All** on Windows.
2. Open your GitHub repository `https://github.com/QuietudeVS/gsb-wine`, choose the **Code** tab, and stay on the **main** branch.
3. Choose **Add file → Upload files**. From the extracted `gsb-docker-v10` directory, upload the updated root-level source files, including `entrypoint.sh`, `serverctl.py`, `compose.yaml`, `.env.example`, `README.md`, `README-QUICKSTART.txt`, `CHANGELOG.md`, and `GITHUB_UPDATE_BROWSER.md`. Upload the `tests/test_tooling.py` file at its correct path (using GitHub's file editor or folder upload). You may upload the other non-proprietary kit files too, but **do not upload your actual Windows game files, game saves, Wine files or any real .env/password**.
4. **Important:** The `.github/workflows/publish-image.yml` workflow already exists in your repo and has not changed. Do not remove it; if hidden `.github` is skipped by your browser, that's fine for this update.
5. Confirm the root of the repository contains `Dockerfile`, `entrypoint.sh`, `serverctl.py`, `compose.yaml`, and the `tests` folder, and that the changed files are committed on `main`.
6. From the repository page click **Releases → Draft a new release**, choose **Create new tag** `v10.1.0`, targeted to **main**, and publish release titled `GSB Docker v10.1.0`.
7. Open **Actions → Publish GSB Wine image to GHCR** and check the workflow for `v10.1.0`. A green check confirms the build/push job finished. If it does not start, use **Run workflow**, selecting the `v10.1.0` tag rather than `main`.
8. Verify `https://github.com/users/QuietudeVS/packages/container/gsb-wine` (the exact package page may vary) is public. On a Linux Docker host, run `docker pull ghcr.io/quietudevs/gsb-wine:v10.1.0` and test `docker run` or `compose.yaml` with your Windows game installation.

**Common previous issue:** Creating a release tag from a commit *before* the Actions workflow was committed prevented manual `workflow_dispatch` on that tag. Always commit the updated files and use the latest `main` commit when creating a release tag.

**If GitHub's file uploader doesn't preserve nested `tests/` paths:** Open the `tests` directory within GitHub, select `test_tooling.py`, click the edit (pencil) icon, paste the new test content, and commit. Do not accidentally put the test at the repository root.

This release is a source change, not a newly published image, until GitHub Actions completes successfully. Updating the source code on GitHub alone does not replace any running user containers.
