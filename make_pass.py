#!/usr/bin/env python3
import argparse, random, secrets, string

SIZE = 64
SAFE = string.ascii_letters + string.digits + "!#$%&()*+,-./:;<=>?@[]^_{|}~"


def cpp_char(c: str) -> str:
    if c == "'":  return r"'\''"
    if c == "\\": return r"'\\'"
    return f"'{c}'"


def build(password: str, seed=None, pad=True):
    if not password.isascii():
        raise ValueError("Password must be ASCII.")
    if len(password) > SIZE:
        raise ValueError(f"Password longer than {SIZE} characters.")
    if len(password) < SIZE:
        if not pad:
            raise ValueError(f"Password must be exactly {SIZE} characters.")
        password += "".join(secrets.choice(SAFE) for _ in range(SIZE - len(password)))

    rng = random.Random(seed) if seed is not None else random.SystemRandom()
    order = list(range(SIZE))
    rng.shuffle(order)
    lines = [f"buffer->PokeByte({i}, {cpp_char(password[i])});" for i in order]
    return lines, password


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("password")
    ap.add_argument("--seed", type=int, default=None, help="reproducible shuffle")
    ap.add_argument("--no-pad", action="store_true", help="require exactly 64 chars")
    a = ap.parse_args()

    lines, final_pw = build(a.password, a.seed, pad=not a.no_pad)
    print("\n".join(lines))
    print(f"\n//Assert(s == \"{final_pw.replace(chr(92), chr(92)*2).replace(chr(34), chr(92)+chr(34))}\");")