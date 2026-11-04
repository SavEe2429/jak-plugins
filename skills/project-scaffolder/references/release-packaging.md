# Release Packaging Decisions

Use this guide when a project is expected to publish or distribute a buildable artifact. Release packaging is conditional on the user's lifecycle and target; it is not implied by the presence of a package manager or a build command.

## Identify the release target

Classify the deliverable before proposing directories or workflows:

| Target | Typical release concerns |
| --- | --- |
| Binary executable application (e.g. PyInstaller, native CLI/GUI) | `packaging/` build definition, `out/<package_name>/` output destination, `onedir` vs `onefile` mode selection, icon/version assets, and platform build scripts |
| Game or application | Supported platform, scenes/entry point, version, artifact naming/layout, build workflow, retention, and installer or archive when requested |
| Reusable Unity UPM package | `package.json`, `Runtime/`, optional `Editor/`, tests, assembly definitions, changelog, version, package archive, and registry or Git distribution |
| Library, CLI, or service package | Native package manifest, registry, version/tag policy, build artifact, release notes, and registry credentials handled through the platform's secret store |
| Plugin, model, or asset bundle | Host compatibility, required files, license/provenance, versioning, archive layout, and delivery channel |
| No distribution in scope | Mark release packaging N/A and do not create publish workflows or empty release directories |

Ask for clarification only when the distribution target, supported platform, or delivery channel changes the planned layout. Keep a Unity game's player build separate from a reusable Unity UPM package: one is a runnable product artifact, the other is an importable dependency.

## Binary Executable Packaging Standard (PyInstaller & Binary Bundlers)

When an application is packaged into standalone binary executables (such as `.exe` on Windows or ELF/Mach-O on Linux/macOS):

### 1. Build Definition Root: `packaging/`
All build definitions, configuration files, and assets necessary to produce binaries must reside under `packaging/`.
- `packaging/`:
  - Build scripts: `build.py`, `build.bat`, or `build.sh` invoking the bundler.
  - Bundler specifications: `<package_name>.spec` (for PyInstaller) or equivalent bundler configurations.
  - Binary assets: application icons (`.ico`, `.png`), Windows version resources (`version.txt`, manifest), and license embeds.
- Keep `packaging/` isolated from core application source code (`src/`).

### 2. Output Artifact Destination: `out/<package_name>/`
Compiled binaries and final packaged distributions must be output to:
`out/<package_name>/`
- Windows examples:
  - `out/<package_name>/<package_name>.exe` (for `onefile` mode)
  - `out/<package_name>/...` (for `onedir` mode, containing `<package_name>.exe` alongside dependencies and supporting runtime libraries)
- Git Hygiene:
  - `out/` and `build/` (intermediate compiler cache) must be declared in `.gitignore` to prevent committing compiled binaries to the repository.

### 3. Packaging Mode Selection: `onedir` vs `onefile`
When planning binary packaging, the agent must prompt the user to choose the desired packaging mode:
- `onedir` (Directory bundle - recommended for complex/large applications):
  - Produces a self-contained directory containing `<package_name>.exe` alongside required runtime libraries, dynamic links (DLLs), and assets.
  - Benefits: Faster startup time (no extraction overhead), simpler incremental updates and debugging.
- `onefile` (Single standalone executable - recommended for lightweight utilities/CLIs):
  - Packs the application and dependencies into a single compressed `.exe` file.
  - Benefits: Clean, single-file distribution without an installer.
  - Tradeoffs: Cold-launch startup is slower because the bootloader must unpack contents into a temporary directory on each run.

### 4. Build Script Example (PyInstaller Integration)
```python
# packaging/build.py
import PyInstaller.__main__
from pathlib import Path

PACKAGE_NAME = "my_app"
ROOT_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT_DIR / "out" / PACKAGE_NAME
WORK_DIR = ROOT_DIR / "build" / PACKAGE_NAME
SPEC_FILE = ROOT_DIR / "packaging" / f"{PACKAGE_NAME}.spec"

def build(mode="onedir"):  # or "onefile"
    args = [
        str(SPEC_FILE),
        f"--distpath={DIST_DIR}",
        f"--workpath={WORK_DIR}",
        "--clean",
        # Keep the packager's interactive confirmation enabled; do not suppress prompts.
    ]
    # Embed internal presentation assets from interfaces/ui
    ui_dir = ROOT_DIR / "src" / PACKAGE_NAME / "interfaces" / "ui"
    if ui_dir.exists():
        args.append(f"--add-data={ui_dir};{PACKAGE_NAME}/interfaces/ui")

    if mode == "onefile":
        args.append("--onefile")
    else:
        args.append("--onedir")
    PyInstaller.__main__.run(args)
```

## Plan concrete outputs

For a confirmed release target, map each applicable item to a file or command in the reviewed plan:

- [ ] Artifact type, platform/registry, output path, and naming convention.
- [ ] Version source and release/tag trigger.
- [ ] Build/package command and the validation that must pass before release.
- [ ] CI release workflow, if the project uses CI and the user wants automated releases. Follow [`references/repository-governance.md`](repository-governance.md) for generic SemVer release automation, changelog promotion, and multi-tier quality gates.
- [ ] Changelog or release notes and a retention policy for generated artifacts.
- [ ] Checksums, SBOM/provenance, or signing only when required by the delivery channel or user.
- [ ] Secret names and storage locations documented without putting credentials in the repository.

Do not report release automation as implemented when only a local build command exists. A build command, dependency lockfile, or CI test workflow is not evidence that an artifact was packaged, published, signed, or uploaded. If the selected profile/provider has no matching template, add a tailored contribution to the reviewed plan or report the item as NOT VERIFIED; do not silently invent a release platform.
