# package_project.py

Packages a Leadwerks 5 project into an AES-256 encrypted zip. It scans your maps and source code for referenced files, follows dependencies recursively, and packs only what is actually used.

## Features

- No arguments: run it from its own folder (the project root).
- Scans all `.map` files and the solution source for path-like strings.
- Follows dependencies recursively (for example `mdl` → `mat` → textures).
- Includes sidecar files (`.phy`, `.pbr`, `.bin`) for models.
- Uses AES-256 (WinZip AES) encryption via `pyzipper`.
- Writes `package_manifest.txt` listing everything included.
- `DEBUG` mode prints the final file list without creating anything.

## Requirements

- Python 3.9+
- `pyzipper`

pyzipper needs to be installed.
if you have issues running this file, just install pyzipper to your current environment, and run it.

## Usage
Place this script in your project root folder, and also `cd` to your project root, then run the python file.

(for example, my project name is The Hallow)

```powershell
cd "D:\leadwerks\The Hallow"
& 'D:\miniconda\python.exe' package_project.py
```

Output: /packages/ folder in your project, including all the files you need to run your game as a portable .exe.

## Configuration

All settings are constants at the top of the script.

| Setting | Purpose |
|---|---|
| `DEBUG` | `True`: print the sorted file list only. No zip, no manifest. |
| `PACKAGE_KEY` | Password used for AES-256 encryption. |
| `OUTPUT_NAME` | Output archive name (default `data.zip`). |
| `MAP_DIRS` | Folders searched for `.map` files (default `["Maps"]`). |
| `SOURCE_DIRS` | Folders scanned for code references (default `["Source","Scripts"]`). |
| `SOURCE_EXTS` | Extensions treated as source and read for references. |
| `ASSET_EXTS` | Extensions that count as packageable assets. |
| `FOLLOW_EXTS` | Extensions whose contents are scanned for further references. |
| `NEVER_INCLUDE_EXTS` | Blacklist, never packaged. |
| `ALWAYS_INCLUDE_EXTS` | Whitelist, always packaged. |
| `EXCLUDE_DIRS` | Folders skipped entirely during scanning. |
| `MAX_SCAN_BYTES` | Maximum bytes read per file when scanning. |

## How it works

1. **Seed:** collect every `.map` file in `MAP_DIRS` and every source file in `SOURCE_DIRS`.
2. **Always-include:** add every file whose extension is in `ALWAYS_INCLUDE_EXTS` to the queue.
3. **Scan:** byte-scan each queued file for path-like strings, both ASCII and UTF-16LE.
4. **Resolve:** match each string against files that exist on disk.
5. **Recurse:** newly found files with an extension in `FOLLOW_EXTS` go back into the queue.
6. **Filter:** remove blacklisted extensions, keep only `ASSET_EXTS`.
7. **Write:** create the encrypted zip and the manifest.

### Path resolution

Because the `.map` format is not documented, the script does not parse it. It finds candidate strings and tries to match them in this order:

1. Relative to the referencing file's folder.
2. Relative to the project root.
3. With leading path segments dropped one at a time.
4. By unique file name anywhere in the project.

If a file name is ambiguous (several matches), all matches are included. A `X::` prefix on a path is stripped before matching.

## Filters explained

### Precedence
