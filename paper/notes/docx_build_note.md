# DOCX build note — environment and math conversion

Recorded 2026-08-23 so the build is reproducible.

## Toolchain

| item | value |
|---|---|
| pandoc used for this build | **3.10.2** (`/opt/homebrew/bin/pandoc`, installed via Homebrew 2026-08-22) |
| target/compatibility floor | **2.9.2.1** — reported by the author to silently render `\Bigl`/`\Bigr`/`\bigl`/`\bigr` as raw TeX with no error |
| build command | `pandoc manuscript_assembled.md -o <out>.docx` (reference doc pending) |
| source of truth | `~/research/papers/draft/section*.md`; `manuscript_assembled.md` is generated and must be regenerated before every build |

## Delimiter-macro portability fix

All 15 occurrences of `\Bigl` / `\Bigr` / `\bigl` / `\bigr` were replaced by
`\left` / `\right` (10 in §4, 5 in §5). These size identically and convert on
every pandoc version, where the `\big*` family fails on 2.9.2.1 — silently, which
is what makes it dangerous: Eq. (3), Eq. (4)'s aligned block and the Corollary's
ceiling would have shipped as raw TeX with a clean build log.

**Verification limit, stated plainly:** the fix was verified on pandoc 3.10.2,
which is what is installed here. **2.9.2.1 is not installed on this machine, so
the failure it fixes was not reproduced locally** — the change is made on the
author's report plus the general portability argument, not on a local repro. If
2.9.2.1 is the environment that matters, the counts below should be re-run there.

Balance was checked after the substitution: §4 has 19 `\left` (excluding one
`\leftarrow`) against 19 `\right`; §5 has 5 against 5.

## Build verification (pandoc 3.10.2)

```
exit=0, stderr = 0 lines, "Could not convert TeX math" = 0

m:oMath 186 | m:oMathPara 38 | m:eqArr 1 | w:drawing 0
cases matrices m:m 3 | branch rows m:mr 10
raw TeX control sequences left in body: 0
```

Reference points on this machine: `last-Mirzazada_NDU_2026_Tezis.docx` has 11
native equations and 0 MathType objects (the target); `Paper6_v11_final.docx` has
0 native equations and 7 images (math pasted as pictures — the anti-pattern).

## How to check the piecewise definitions — the `m:eqArr` heuristic is wrong

The brief's check "zero `m:eqArr` means the piecewise cases collapsed" does not
test what it intends. **Pandoc encodes `\begin{cases}` as a braced matrix**
(`m:m` containing `m:mr` rows inside an `m:d` delimiter), not as an equation
array. The single `m:eqArr` in this build comes from the `\begin{aligned}` in
Eq. (4).

The check that does test it:

- `m:m` = **3** — one per `cases` block (trap, tri, `g(a)`)
- `m:mr` = **10** — branch rows, matching 4 + 3 + 3

and the first block's rows extract as four distinct branches:

```
row 1: 0,            x < a or x > d
row 2: (x−a)/(b−a),  a ≤ x < b
row 3: 1,            b ≤ x ≤ c
row 4: (d−x)/(d−c),  c < x ≤ d
```

which is the opposite of the failure mode in the thesis file, where `μ_HIGH`'s
branches ran together on one line.

## Reading the equation text dump — a second misleading check

Stripping tags from the OMML and searching for `⌈` or `∏` returns nothing, which
looks like a conversion failure and is not. OMML carries delimiters and n-ary
operators as **attributes**, not text nodes. Verified present in this build:

- `m:begChr` / `m:endChr` = 30 each, with characters `( { | ‖ ⌈` and `) | ‖ ⌉`
- `m:nary` = 30, with operator characters `∏` and `∑`
- plus `m:f` 17 fractions, `m:sub` 58, `m:sup` 38

So the Corollary's ceiling, the sup-norms, the products and the sums are all
structurally present.

## Still to do before the final build

Reference doc (Springer EMSE Word template if obtainable, else a clean academic
one), three figures, appendices A–F, Tables 1a–c, and the page count.
