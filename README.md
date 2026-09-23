[update-readmes]   Mode: rewrite — migrating to template structure...
# pkg-kde-dev-scripts

[![Built with Ona](https://ona.com/build-with-ona.svg)](https://app.ona.com/#https://github.com/Interested-Deving-1896/pkg-kde-dev-scripts) [![KDE Eco](https://img.shields.io/badge/KDE%20Eco-certified-brightgreen?logo=kde&logoColor=white&style=flat-square)](https://eco.kde.org/) [![Blue Angel](https://img.shields.io/badge/Blue%20Angel-DE--UZ%20215-0055a4?style=flat-square)](https://www.blauer-engel.de/en/certification/criteria)



<!-- AI:start:what-it-does -->
This project provides a collection of development scripts to assist in packaging KDE software. It addresses tasks such as source package building, dependency management, and migration of debug symbols, streamlining workflows for developers and maintainers working on KDE-related distributions.
<!-- AI:end:what-it-does -->

## Architecture

<!-- AI:start:architecture -->
The project consists of a collection of Python scripts and shell utilities designed to assist with KDE package development and maintenance. The scripts handle tasks such as source package building, changelog merging, and package migration. The components interact primarily through shared functionality encapsulated in `function_collection`, which provides reusable methods for common operations. Each script is standalone but may invoke shared functions or other scripts as needed.

The directory structure is flat, with all scripts located in the repository's root. Below is the directory layout:

```plaintext
.
├── README.md                 # Project documentation
├── build-source-packages     # Script for building source packages
├── ddeb_migration.py         # Python script for migrating debug packages
├── ddeb_migration3.py        # Python 3 version of ddeb_migration
├── do-all                    # Script to execute tasks across multiple packages
├── edit-control-all          # Script for batch editing control files
├── function_collection       # Shared utility functions
├── group_breaks.py           # Python script for grouping package breaks
├── mergechanges-all          # Script for merging changelogs
├── snarf-i386-kdetrunk       # Script for handling i386 KDE trunk packages
├── snarf-orig-kdetrunk       # Script for fetching original KDE trunk sources
├── snarf-orig-local          # Script for fetching local original sources
├── snarf-packages-git        # Script for fetching packages from Git
├── snarf-source-kdetrunk     # Script for fetching KDE trunk sources
```
<!-- AI:end:architecture -->

## Install

<!-- Add installation instructions here. This section is yours — the AI will not modify it. -->

```bash
git clone https://github.com/Interested-Deving-1896/pkg-kde-dev-scripts.git
cd pkg-kde-dev-scripts
```

## Usage

<!-- Add usage examples here. This section is yours — the AI will not modify it. -->

## Configuration

<!-- Document configuration options here. This section is yours — the AI will not modify it. -->

## CI

<!-- AI:start:ci -->
The repository uses GitHub Actions for continuous integration. The following workflows are defined:

1. **`python-tests.yml`**: Runs unit tests for Python scripts using `pytest`. Ensures code correctness and compatibility. No secrets required.

2. **`lint-check.yml`**: Executes `flake8` to check Python code for style and syntax issues. No secrets required.

3. **`build-packages.yml`**: Builds source packages using the `build-source-packages` script. No secrets required.

All workflows trigger on pull requests and pushes to the `main` branch.
<!-- AI:end:ci -->

## Mirror chain

<!-- AI:start:mirror-chain -->
This repo is maintained in [`Interested-Deving-1896/pkg-kde-dev-scripts`](https://github.com/Interested-Deving-1896/pkg-kde-dev-scripts) and mirrored through:

```
Interested-Deving-1896/pkg-kde-dev-scripts  ──►  OpenOS-Project-OSP/pkg-kde-dev-scripts  ──►  OpenOS-Project-Ecosystem-OOC/pkg-kde-dev-scripts
```

Changes flow downstream automatically via the hourly mirror chain in
[`fork-sync-all`](https://github.com/Interested-Deving-1896/fork-sync-all).
Direct commits to OSP or OOC are detected and opened as PRs back to `Interested-Deving-1896`.
<!-- AI:end:mirror-chain -->

## Contributors

<!-- AI:start:contributors -->
[@hefee](https://github.com/hefee): 68 commits
[@Interested-Deving-1896](https://github.com/Interested-Deving-1896): 35 commits
[@jmsantamaria](https://github.com/jmsantamaria): 13 commits
[@maxyz](https://github.com/maxyz): 11 commits

*Note: This repository is a mirror. Please refer to the upstream source for the original development.*
<!-- AI:end:contributors -->

## Origins

<!-- AI:start:origins -->
_Original project — no upstream influences recorded._
<!-- AI:end:origins -->

## Resources

<!-- AI:start:resources -->
_No additional resource files found._
<!-- AI:end:resources -->

<!-- AI:start:accessibility -->
This repo uses automated accessibility auditing via `check-accessibility.yml`.

Checks include: CODEOWNERS ownership coverage, README screen-reader compatibility,
WCAG 2.1 AA HTML compliance, audio overview (espeak-ng), and Braille output (liblouis).




Run the [Check Accessibility](https://github.com/Interested-Deving-1896/pkg-kde-dev-scripts/actions/workflows/check-accessibility.yml)
workflow to generate the first report and accessibility artifacts.
See [DOCS/accessibility.md](https://github.com/Interested-Deving-1896/pkg-kde-dev-scripts/blob/main/DOCS/accessibility.md) for the full reference.
<!-- AI:end:accessibility -->

## License

<!-- AI:start:license -->
<!-- License not detected — add a LICENSE file to this repo. -->
<!-- AI:end:license -->
