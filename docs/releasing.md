# Release process

RunEXE's Linux release workflow builds frozen x86-64 binaries, packages them for common Linux distributions, installs them in clean containers, and publishes a GitHub release only after every required smoke test passes.

## Release outputs

The workflow publishes:

- glibc portable desktop archive (`.tar.gz`)
- Debian/Ubuntu package (`.deb`)
- Fedora/RPM package (`.rpm`)
- Arch Linux package (`.pkg.tar.zst`)
- musl/Alpine CLI archive (`.tar.gz`)
- `SHA256SUMS`

Filenames include the tag plus a short hash-derived label where applicable. Native package versions come from the numeric project version in `pyproject.toml` and `runexe/__init__.py`.

## Build baselines

- Desktop glibc build: Ubuntu 22.04 / glibc 2.35
- musl CLI build: Alpine 3.22
- Frozen executable builder: PyInstaller 6.22.2

The glibc bundle includes the Qt QML, Qt Quick, Qt Quick Controls, and Qt Quick Dialogs modules used by the desktop shell. The musl artifact is CLI-only.

## Smoke-test matrix

Before publication, the workflow installs and launches the output in clean containers:

| Environment | Artifact |
| --- | --- |
| Debian bookworm | `.deb` |
| Ubuntu 22.04 | `.deb` |
| Fedora | `.rpm` |
| Arch Linux | `.pkg.tar.zst` |
| Alpine 3.22 | musl `.tar.gz` |

The desktop package tests run the CLI and start the Qt application offscreen. The Alpine smoke test verifies the frozen CLI.

## Tag behavior

The workflow is stored in `.github/workflows/release-linux.yml` and must be present in the tagged commit.

Push release tags individually. GitHub can suppress tag events when many tags are pushed together, and tags created from another workflow using the default `GITHUB_TOKEN` do not necessarily trigger downstream workflows.

If a tag event does not start the build, use **Actions → Linux release binaries → Run workflow** and provide the existing tag.

Annotated tags can produce both `push` and `create` events. The workflow serializes runs for the same tag. A redundant queued run can be cancelled once the primary run is healthy.

## Publication safety

The workflow leaves a new GitHub release in draft state until every required artifact has been downloaded into the publish job and checksums have been generated. It confirms that the tag still points at the exact commit that was built and tested.

Published releases are not overwritten on rerun. If a release is already published, rerun artifacts remain available from the workflow run instead of replacing published assets.

Draft releases can be retried safely.

## Pull requests

Pull requests that change the release workflow, build scripts, package scripts, release tests, or project metadata build and smoke-test the package formats without creating or modifying a GitHub release.

## Release checklist

1. Update `pyproject.toml` and `runexe/__init__.py` to the same numeric version.
2. Add the release section to `CHANGELOG.md`.
3. Run the project tests, Ruff checks, and build verification appropriate to the change.
4. Commit and push the exact release state to `main`.
5. Create an annotated tag, for example `git tag -a v1.0.0 -m "Release version 1.0.0"`.
6. Push the tag by itself.
7. Watch the Linux release workflow through all package and smoke-test jobs.
8. Confirm the GitHub release contains every expected artifact plus `SHA256SUMS`.
