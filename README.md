# package_project.py

Packages a Leadwerks 5 project with AES-256 encryption. It scans your maps and source code for referenced files, follows dependencies recursively, and packs only what is actually used.

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

# make_pass.py
## Password tool for `Encription.cpp` (Leadwerks)

Prints C++ code that sets your own package password in `Source/Encription.cpp`. By default, Leadwerks' own default secret is used in this repo, and that secret is public. To encrypt packages with your own secret, replace the relevant lines in `Source/Encription.cpp` (from line 9 onward) with this script's output.

**If you don't plan to change your password, or you aren't sure what this does, skip this tool.**

## What it does

- The password is always built to exactly 64 bytes (`SIZE = 64`).
- Shorter passwords are padded with random characters from a safe set (letters, digits and a list of punctuation that needs no escaping in C++ char literals).
- The 64 `buffer->PokeByte(index, 'c');` lines are printed in shuffled order, so the password does not read left to right in the source.
- A commented `Assert(...)` line prints the final password, including any padding.

## Requirements

- Python 3
- No extra packages

## Usage

```
python make_password.py <password> [--seed N] [--no-pad]
```

| Option | Meaning |
|---|---|
| `password` | ASCII only, at most 64 characters |
| `--seed N` | Fixed seed for the line shuffle, so the same output is reproducible |
| `--no-pad` | Refuse anything that isn't exactly 64 characters instead of padding |

Without `--seed`, the order of the lines is random every run. The padding characters are always random (via `secrets`), even with `--seed`. Only the shuffle order is reproducible. To get identical output every time, use a password that is exactly 64 characters with `--no-pad` and a fixed `--seed`.

## Example

```
python make_password.py "my-secret" --seed 42
```

Output (shortened):

```
buffer->PokeByte(17, 'x');
buffer->PokeByte(3, 'c');
...
//Assert(s == "my-secret<55 random padding chars>");
```

## Applying it

1. Run the script and copy the `PokeByte` lines.
2. In `Source/Encription.cpp`, replace the existing lines starting at line 9 with the copied block.
3. Keep the `//Assert(...)` line (it is a comment). The password inside it is the actual final key, including padding. Copy that value out and store it somewhere safe.
4. Rebuild the game or engine so the new key is compiled in.
5. Use the same final password for your packager (`PACKAGE_KEY`). If the two don't match, the game can't open the packages.

## Notes and warnings

- **The password in the `//Assert` line is plaintext.** Don't commit or share it. Delete that line, or the comment, before committing if the repo is public.
- **Padding changes the key.** If you give a short password without `--no-pad`, the random padding becomes part of the key. Re-running the script later gives a different key, so save the printed one.
- **Quote the argument properly in your shell.** Characters like `!`, `$`, `&`, `(`, `)` and `;` need quotes. In bash, `!` also triggers history expansion. A password starting with `-` should be passed after `--`, for example `python make_password.py -- "-secret"`.
- **Shell history keeps the password.** Clear it afterwards if that matters.
- **This is obfuscation, not strong protection.** Shuffling the byte order only makes the key harder to read in the source. Anyone with the compiled binary can extract it. It stops casual unpacking, not a determined attacker.
- **Non-ASCII passwords are rejected**, and so are passwords longer than 64 characters.
- **Control characters:** the script doesn't escape them, only `'` and `\`. Avoid them.

## Troubleshooting

| Message | Cause |
|---|---|
| `Password must be ASCII.` | Non-ASCII characters in the password |
| `Password longer than 64 characters.` | Shorten it |
| `Password must be exactly 64 characters.` | `--no-pad` was set and the length isn't 64 |
