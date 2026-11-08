# Dependency notices

Date: 2026-11-08

Summary: Luomu CAD application source is Copyright (c) 2026 luomufanye-cloud and is distributed under the repository MIT license. External libraries are installed separately under their own licenses.

## Current component implementation

The current release implements parameterized component symbols, wall openings and joins in src/luomu_cad/component_library.py. Public component identifiers and numeric interface dimensions remain compatible. The drawing programs and newly designed parameterized outlines are maintained by Luomu CAD; no retired component implementation is included in this release.

## Optional solid-model runtime

Project state, authored-script execution, retry records, feature matching and comparison reports are implemented in src/luomu_cad/solid_engine.py. build123d, OpenCascade bindings, NumPy, Matplotlib and Pillow provide separately installed geometry and rendering libraries. Their actual package names, versions, licenses and notices remain in the runtime distributions; exact installed versions are recorded in references/solid-runtime-lock.json.

The repository source archives do not bundle those libraries or binaries. The repository MIT license covers the project's application code, not separately installed dependencies. Further notices for document/vision dependencies are retained in references/vision-upstream-license.md and the corresponding installed distributions.

## Component reference documents

Current implementation and verification information is recorded in references/house-plan-components.md and references/house-plan-components-source.json. Older releases and their applicable notices remain in version history. Previous executable files and notices were retained outside the published source tree for replacement verification.

## Other dependencies

See DEPENDENCIES.md for the library inventory. Installed dependencies, model weights and user-provided assets retain their respective licenses. User CAD files, runtime logs and private replacement baselines are not included in release archives.
