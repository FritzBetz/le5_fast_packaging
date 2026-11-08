DEBUG = False
import shutil
import os
import re
import sys
from pathlib import Path

import pyzipper

PACKAGE_KEY = "k6f8cpOkrnhGkwIApwGKBbgrWHlYff3gMKkixPCxvPqhv9Yyc22DtSiydftPU2cx"

OUTPUT_DIR = "Packages"

MAP_DIRS = ["Maps"]
SOURCE_DIRS = ["Source"]
SOURCE_EXTS = {".cpp", ".h", ".hpp", ".c", ".cc", ".lua", ".py", ".json", ".cs", ".txt", ".ini"}

ASSET_EXTS = {
    ".glb", ".gltf", ".bin", ".mat", ".mdl", ".wav", ".mp3", ".ogg", ".tex", ".dds",
    ".png", ".jpg", ".jpeg", ".tga", ".bmp", ".pbr", ".phy", ".sbx", ".map", ".lua",
    ".shader", ".spv", ".frag", ".vert", ".geom", ".tesc", ".tese", ".comp", ".fx",
    ".json", ".fbx", ".obj", ".ttf", ".otf", ".pfx", ".prefab", ".mp4", ".ogv", ".pfb"
}
FOLLOW_EXTS = {".mat", ".mdl", ".gltf", ".glb", ".json", ".lua", ".pfx", ".pfb",
               ".shader", ".sbx", ".map", ".tex", ".pbr", ".fx"}

NEVER_INCLUDE_EXTS = {
    ".bat", ".cpp", ".env", ".filters", ".h", ".hpp", ".lib", ".manifest",
    ".py", ".pyc", ".rc", ".sln", ".vcxproj", ".txt", ".md",
}
ALWAYS_INCLUDE_EXTS = {
    ".comp", ".fam", ".frag", ".fx", ".geom", ".glsl", ".lua", ".map", ".mp3",
    ".spv", ".tesc", ".tese", ".ttf", ".ultra", ".vert", ".wav", ".json",
}

# stuff to be always added if found inside a used .mdl file (in a map layer or else) 
MDL_SIDE_EXTS = {".mat", ".shader", ".frag", ".vert", ".geom", ".tesc",
                 ".tese", ".comp", ".fx", ".glsl", ".spv"}
MDL_FOLDER_SIBLINGS = True



# stuff to be added form the root folder (only .exe and dlls)
LOOSE_EXTS = {".exe", ".dll"}
LOOSE_SKIP_STEM_SUFFIX = "_d"

ASSET_EXTS |= ALWAYS_INCLUDE_EXTS
ASSET_EXTS -= NEVER_INCLUDE_EXTS

EXCLUDE_DIRS = {".git", ".vs", ".vscode", "__pycache__", "build", "debug", "release",
                "x64", "bin", "obj", "node_modules", "backup", "entity definitions",
                "legal", "coding_tools", "packages"}
EXCLUDE_FILES = {"package_manifest.txt"}
MAX_SCAN_BYTES = 256 * 1024 * 1024

ROOT = Path(__file__).resolve().parent
SOURCE_ROOTS = [(ROOT / d).resolve() for d in SOURCE_DIRS]
_EXTS_SORTED = sorted(ASSET_EXTS, key=len, reverse=True)
EXT_PATTERN = "|".join(re.escape(e[1:]) for e in _EXTS_SORTED)
TOKEN_RE_B = re.compile(
    rb"[\w\-. /\\:()\[\]+@#$%&!~,]{1,300}?\.(?:" + EXT_PATTERN.encode() + rb")(?![A-Za-z0-9_])",
    re.IGNORECASE)

_WEXT = b"|".join(b"".join(bytes([ord(c)]) + b"\x00" for c in e[1:]) for e in _EXTS_SORTED)
TOKEN_RE_W = re.compile(
    rb"(?:[\w\-. /\\:()\[\]+@#$%&!~,]\x00){1,300}?\.\x00(?:" + _WEXT + rb")(?![\w]\x00)",
    re.IGNORECASE)


def norm(s):
    s = s.replace("\\", "/").strip().strip("\"'")
    if "::" in s:
        s = s.split("::", 1)[1]
    while s.startswith("./"):
        s = s[2:]
    return s.lstrip("/").lower()


def is_blacklisted(p):
    if p.suffix.lower() in NEVER_INCLUDE_EXTS:
        return True
    rp = p.resolve()
    for sr in SOURCE_ROOTS:
        try:
            rp.relative_to(sr)
            return True
        except ValueError:
            pass
    return False


def build_index():
    by_rel, by_name = {}, {}
    for dp, dns, fns in os.walk(ROOT):
        dns[:] = [d for d in dns if d.lower() not in EXCLUDE_DIRS]
        for fn in fns:
            p = Path(dp) / fn
            if p.parent == ROOT:
                continue
            if fn.lower() in EXCLUDE_FILES or p.suffix.lower() not in ASSET_EXTS:
                continue
            if is_blacklisted(p):
                continue
            rel = p.relative_to(ROOT).as_posix().lower()
            by_rel[rel] = p
            by_name.setdefault(fn.lower(), []).append(p)
    return by_rel, by_name


def resolve(token, origin, by_rel, by_name):
    t = norm(token)
    if not t:
        return None
    if origin is not None:
        try:
            orel = (origin.parent / t).resolve().relative_to(ROOT).as_posix().lower()
            if orel in by_rel:
                return by_rel[orel]
        except Exception:
            pass
    parts = re.split(r"(?<=[/ ])", t)
    for i in range(len(parts)):
        cand = "".join(parts[i:]).strip()
        if cand in by_rel:
            return by_rel[cand]
    base = t.rsplit("/", 1)[-1].strip()
    hits = by_name.get(base, [])
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        print(f"  [ambiguous] {base}: {len(hits)} matches, including all")
        return hits
    return None


def extract_tokens(data):
    for m in TOKEN_RE_B.finditer(data):
        yield m.group(0).decode("latin-1")
    for m in TOKEN_RE_W.finditer(data):
        try:
            yield m.group(0).decode("utf-16-le")
        except Exception:
            pass


def scan_file(path, by_rel, by_name):
    found = set()
    try:
        if path.stat().st_size > MAX_SCAN_BYTES:
            return found
        data = path.read_bytes()
    except OSError:
        return found
    for tok in extract_tokens(data):
        r = resolve(tok, path, by_rel, by_name)
        if r is None:
            continue
        for p in (r if isinstance(r, list) else [r]):
            if p != path and not is_blacklisted(p):
                found.add(p)
    return found

def follow_from(starts, by_rel, by_name):
    reach, q, seen = set(starts), list(starts), set()
    while q:
        cur = q.pop()
        if cur in seen:
            continue
        seen.add(cur)
        if cur.suffix.lower() not in FOLLOW_EXTS:
            continue
        for p in scan_file(cur, by_rel, by_name):
            if p not in reach:
                reach.add(p)
                q.append(p)
    return reach


def build_side_index(by_name):
    return {n: ps for n, ps in by_name.items()
            if Path(n).suffix.lower() in MDL_SIDE_EXTS}


def scan_mdl_deep(path, side_index):
    try:
        data = path.read_bytes().lower()
    except OSError:
        return set()
    spans = []
    for name in side_index:
        for enc in (name.encode("latin-1", "ignore"), name.encode("utf-16-le")):
            i = data.find(enc)
            while i != -1:
                spans.append((i, i + len(enc), name))
                i = data.find(enc, i + 1)
    keep = set()
    for s, e, n in spans:
        if not any(s2 <= s and e <= e2 and (e2 - s2) > (e - s) for s2, e2, _ in spans):
            keep.add(n)
    out = set()
    for n in keep:
        hits = side_index[n]
        local = [h for h in hits if path.parent in h.parents or h.parent == path.parent]
        out.update(local or hits)
    return out


def mdl_siblings(path):
    out = set()
    for p in path.parent.iterdir():
        if p.is_file() and p.suffix.lower() in MDL_SIDE_EXTS:
            out.add(p)
    return out

def collect_files(dirs, exts=None):
    out = []
    for d in dirs:
        base = ROOT if d == "." else ROOT / d
        if not base.exists():
            continue
        for dp, dns, fns in os.walk(base):
            dns[:] = [x for x in dns if x.lower() not in EXCLUDE_DIRS]
            for fn in fns:
                p = Path(dp) / fn
                if exts is None or p.suffix.lower() in exts:
                    out.append(p)
    return out


def collect_always_include():
    out = []
    for dp, dns, fns in os.walk(ROOT):
        dns[:] = [d for d in dns if d.lower() not in EXCLUDE_DIRS]
        for fn in fns:
            p = Path(dp) / fn
            if p.parent == ROOT:
                continue
            if fn.lower() in EXCLUDE_FILES:
                continue
            if p.suffix.lower() in ALWAYS_INCLUDE_EXTS and not is_blacklisted(p):
                out.append(p)
    return out

def group_by_top(files):
    groups = {}
    for p in files:
        parts = p.relative_to(ROOT).parts
        key = parts[0] if len(parts) > 1 else "_root"
        groups.setdefault(key, []).append(p)
    return groups

def collect_loose():
    out = []
    for p in ROOT.iterdir():
        if not p.is_file() or p.suffix.lower() not in LOOSE_EXTS:
            continue
        if p.stem.lower().endswith(LOOSE_SKIP_STEM_SUFFIX):
            continue
        out.append(p)
    return sorted(out, key=lambda p: p.name.lower())

def main():
    print(f"Project root: {ROOT}")
    by_rel, by_name = build_index()
    print(f"Indexed {len(by_rel)} candidate asset files")

    maps = [m for m in collect_files(MAP_DIRS, {".map"}) if not is_blacklisted(m)]
    sources = collect_files(SOURCE_DIRS, SOURCE_EXTS)
    if not maps:
        print("No .map files found.")
        sys.exit(1)
    print(f"{len(maps)} map(s), {len(sources)} source file(s) (read-only, never packaged)")

    used, queue = set(), []
    for m in maps:
        used.add(m)
        queue.append(m)

    always = collect_always_include()
    print(f"{len(always)} always-include file(s)")
    for p in always:
        if p not in used:
            used.add(p)
            queue.append(p)

    for s in sources:
        print(f"[read-only] {s.relative_to(ROOT).as_posix()}")
        for p in scan_file(s, by_rel, by_name):
            if p not in used:
                used.add(p)
                queue.append(p)

    used = {p for p in used if not is_blacklisted(p)}
    queue = [p for p in queue if not is_blacklisted(p)]

    seen = set()
    while queue:
        cur = queue.pop()
        if cur in seen:
            continue
        seen.add(cur)
        print(f"[scan] {cur.relative_to(ROOT).as_posix()}")
        if cur.suffix.lower() not in FOLLOW_EXTS:
            continue
        for p in scan_file(cur, by_rel, by_name):
            if p not in used:
                used.add(p)
                queue.append(p)

    map_reach = follow_from(maps, by_rel, by_name)
    side_index = build_side_index(by_name)
    done = set()
    while True:
        mdls = [p for p in map_reach if p.suffix.lower() == ".mdl" and p not in done]
        if not mdls:
            break
        new = set()
        for m in mdls:
            done.add(m)
            found = scan_mdl_deep(m, side_index)
            if MDL_FOLDER_SIBLINGS:
                found |= mdl_siblings(m)
            found = {p for p in found if not is_blacklisted(p)}
            for p in found - used:
                print(f"[mdl-dep] {m.name} -> {p.relative_to(ROOT).as_posix()}")
            new |= found
        map_reach |= follow_from(new - map_reach, by_rel, by_name)
        map_reach |= new
    used |= {p for p in map_reach if not is_blacklisted(p)}

    for p in list(used):
        if p.suffix.lower() in {".mdl", ".glb", ".gltf"}:
            for ext in (".phy", ".pbr", ".bin"):
                side = p.with_suffix(ext)
                if side.exists() and not is_blacklisted(side):
                    used.add(side)

    files = sorted((p for p in used if not is_blacklisted(p)),
                   key=lambda p: p.as_posix().lower())

    leaked = [p for p in files if is_blacklisted(p)]
    if leaked:
        print("ABORT: blacklisted files in package list:")
        for p in leaked:
            print(p.relative_to(ROOT).as_posix())
        sys.exit(1)

    groups = group_by_top(files)    
    loose = collect_loose()

    if DEBUG:
        total = sum(p.stat().st_size for p in files)
        print("\n==== DEBUG: archives and files that would be packaged ====")
        for name in sorted(groups, key=str.lower):
            print(f"\n[{name}.zip] {len(groups[name])} files")
            for p in groups[name]:
                print("  " + p.relative_to(ROOT).as_posix())
        print(f"\n[loose files copied as-is] {len(loose)}")
        for p in loose:
            print("  " + p.name)
        print(f"\n{len(groups)} archives, {len(files)} files, {total/1048576:.1f} MiB raw "
              f"(of {len(by_rel)} indexed asset files). Nothing written.")
        return

    out_dir = ROOT / OUTPUT_DIR
    out_dir.mkdir(exist_ok=True)
    for old in out_dir.glob("*.zip"):
        old.unlink()

    total_raw, total_zip = 0, 0
    for name in sorted(groups, key=str.lower):
        out_path = out_dir / f"{name}.zip"
        with pyzipper.AESZipFile(out_path, "w", compression=pyzipper.ZIP_DEFLATED,
                                 encryption=pyzipper.WZ_AES) as zf:
            zf.setpassword(PACKAGE_KEY.encode("utf-8"))
            zf.setencryption(pyzipper.WZ_AES, nbits=256)
            for p in groups[name]:
                zf.write(p, p.relative_to(ROOT).as_posix())
                total_raw += p.stat().st_size
        total_zip += out_path.stat().st_size
        print(f"[{name}.zip] {len(groups[name])} files, {out_path.stat().st_size/1048576:.1f} MiB")

    print(f"\n[loose files copied as-is] {len(loose)}")
    for p in loose:
        shutil.copy2(p, out_dir / p.name)
        print(f"[copy] {p.name}")

    print("\n==== DONE ====")
    print(f"{len(groups)} archives, {len(files)} files ({total_raw/1048576:.1f} MiB raw) "
          f"-> {total_zip/1048576:.1f} MiB in {OUTPUT_DIR}/")
    (out_dir / "package_manifest.txt").write_text(
        "\n".join(p.relative_to(ROOT).as_posix() for p in files), encoding="utf-8")


if __name__ == "__main__":
    main()