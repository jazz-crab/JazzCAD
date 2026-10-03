#!/usr/bin/env python3
"""Check the JazzCAD theme files before they go anywhere near a build.

FreeCAD reads the tokens of a stylesheet through an expression engine (Parser.cpp:
lighten/darken/blend) and falls back through three sources when a token is
missing, so a mistake in the YAML is not caught by the compiler and is not
caught by a failed build either: it is caught by the window looking wrong, which
is the most expensive way to find out.

This reads the stylesheet and the parameter file together and answers the three
questions that actually bite:

  1. does every token the stylesheet asks for have a value?
  2. does every token the YAML defines actually get used, and does it parse?
  3. do the colours stay inside the reference palette?

It needs no FreeCAD, no Qt and no network. Run it from the root of the tree:

    python3 tools/check-jazzcad-theme.py

Exits non-zero when something is wrong, so it can sit in a hook.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# The reference palette of JazzCAD. A colour outside this set is not a mistake
# on its own - the solver needs a red that is not the palette's red - but it is
# worth being able to say so.
PALETTE = {
    "#1a1b26": "bg",
    "#16161e": "bg-alt",
    "#1f2335": "bg-popup",
    "#24283b": "bg-soft",
    "#283457": "bg-select",
    "#2f3b54": "border",
    "#3d4d6e": "border-hover (derived)",
    "#c0caf5": "fg",
    "#a9b1d6": "fg-dark",
    "#565f89": "comment",
    "#f7768e": "red",
    "#ff9e64": "orange",
    "#e0af68": "yellow",
    "#9ece6a": "green",
    "#7dcfff": "cyan",
    "#7aa2f7": "blue",
    "#bb9af7": "magenta",
    "#9d7cd8": "purple",
}

# Colours that are a shade of a reference colour rather than the colour itself,
# with the key that earns the exemption. Every entry has to say why: "it looked
# nicer" is not a reason, and this list is the place a drift would hide.
DERIVED = {
    # A paler red, so "the solver gave up" is visible without looking like the
    # red of a conflict that must be fixed.
    "#ff9090": "SketcherSolverFailedColor",
    # The border one step brighter, for hover; the palette's border is flat.
    "#3d4d6e": "GeneralBorderHoverColor",
}

# The colour functions the engine knows (StyleParameters/Parser.cpp). Anything
# else in an expression is a typo that will not be reported until the theme is
# loaded, so it is checked here.
FUNCTIONS = {"lighten", "darken", "blend", "shade", "shades"}

# Tokens the stylesheet asks for that are NOT colours: the theme editor writes
# them as strings (a size, a folder name) and the engine passes them through.
SCALAR_TOKENS = {
    "InputFieldBorderRadius",
    "ToolbarButtonsPadding",
    "IconsLocationFolderName",
}

HERE = Path(__file__).resolve().parent.parent
STYLESHEET = HERE / "src/Gui/Stylesheets/FreeCAD.qss"
THEMES = HERE / "src/Gui/Stylesheets/parameters"


# A token name may START WITH A DIGIT: @3DViewBackgroundRefColor is one, so
# the character class cannot begin with [A-Za-z]. Getting this wrong makes the
# checker call a used token unused, which is worse than not checking at all.
TOKEN = r"@([A-Za-z0-9][A-Za-z0-9_]*)"


def qss_tokens(text: str) -> set[str]:
    """Every @Token the stylesheet asks for.

    The comment block at the top of the file lists the same tokens one per line
    that the rules below use; both are wanted, so both are taken.
    """
    return set(re.findall(TOKEN, text))


def strip_comment(line: str) -> str:
    """The line without its trailing comment.

    A '#' ONLY starts a comment when it begins a word. A colour is '#' followed
    by six hex digits and never stands in for one: cutting the line at the first
    '#' regardless turns `TextForegroundColor: "#c0caf5"` into a key with an
    empty value, and the checker then passes a file whose colours it never read.
    """
    out: list[str] = []
    for index, char in enumerate(line):
        if char == "#" and (index == 0 or line[index - 1] in " \t"):
            break
        out.append(char)
    return "".join(out)


def read_theme(path: Path) -> dict[str, str]:
    """The key: value pairs of one parameter file, in order, with comments out."""
    params: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = strip_comment(raw).strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        params[key.strip()] = value.strip().strip('"')
    return params


def check_functions(name: str, value: str) -> list[str]:
    """Names called in an expression that the engine does not have."""
    problems = []
    for called in re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(", value):
        if called not in FUNCTIONS:
            problems.append(
                f"{name}: calls `{called}(`, which the theme engine has no such function"
            )
    return problems


def check_literals(name: str, value: str) -> list[str]:
    """Colours written out that are not in the reference palette.

    A solver shade is allowed to leave the palette: the constraint colours carry
    meaning, and a red that is a shade of the palette's red reads as "less
    alarming" where an exact copy would read as "the same alarm". The shades that
    are meant to be off-palette are named in DERIVED; anything else that is not
    in the reference set is a stray.
    """
    problems = []
    for colour in re.findall(r"#[0-9A-Fa-f]{6}", value):
        low = colour.lower()
        if low not in PALETTE and low not in DERIVED:
            problems.append(
                f"{name}: {colour} is neither one of the {len(PALETTE)} reference colours nor a declared shade"
            )
    return problems


def main() -> int:
    if not STYLESHEET.is_file():
        print(f"no stylesheet at {STYLESHEET}")
        return 2

    used = qss_tokens(STYLESHEET.read_text(encoding="utf-8"))
    themes = sorted(THEMES.glob("*.yaml"))
    if not themes:
        print(f"no parameter file under {THEMES}")
        return 2

    problems: list[str] = []
    notes: list[str] = []

    for theme in themes:
        params = read_theme(theme)
        defined = set(params)

        # 1. Every token the stylesheet asks for has a value here or upstream.
        #    Upstream means: the user's own parameters, or the built-in defaults
        #    in ParameterManager.h (ThemeAccentColor1..3, BackgroundColor). Only
        #    the first fallback list is written down here.
        built_in = {
            "ThemeAccentColor1",
            "ThemeAccentColor2",
            "ThemeAccentColor3",
            "BackgroundColor",
        }
        missing = sorted(used - defined - built_in)
        for token in missing:
            problems.append(
                f"{theme.name}: the stylesheet asks @{token} and this file does not answer"
            )

        # 2. Keys nothing reads are dead weight, and a typo in one of them is a
        #    colour that silently stays the stock one. A key counts as read when
        #    the stylesheet asks for it OR another key refers to it: most of the
        #    shades are referenced by the expressions of their own file and are
        #    never named in the stylesheet.
        referred = set()
        for value in params.values():
            referred |= set(re.findall(TOKEN, value))
        unused = sorted(defined - used - referred)
        for key in unused:
            # A note and not a problem: the stock themes carry shades nobody asks
            # for either, and a theme is allowed to as well. What it is NOT
            # allowed to do is define a key the stylesheet wants under a name it
            # does not - and that is caught above, as a missing token.
            notes.append(f"{theme.name}: `{key}` is defined but nothing reads it")

        # 3. Expressions and colours.
        #
        #    The palette binds JAZZCAD only. The stock themes are not bound by
        #    it and are left exactly as they are: a checker that failed on the
        #    shipped themes would be reporting somebody else's palette, and
        #    would be switched off within a week.
        ours = theme.name.startswith("JazzCAD")
        for key, value in params.items():
            problems += check_functions(key, value)
            if ours and key not in SCALAR_TOKENS:
                problems += check_literals(key, value)

        # 4. A theme that does not name its own colours is not a theme.
        if "PrimaryColor" not in defined:
            problems.append(
                f"{theme.name}: no PrimaryColor - the stylesheet would fall through entirely"
            )

    print(f"stylesheet : {STYLESHEET.relative_to(HERE)}")
    print(f"tokens used: {len(used)}")
    print(f"themes     : {', '.join(t.name for t in themes)}")
    print()

    for note in notes:
        print(f"note: {note}")
    if notes:
        print()

    if problems:
        print(f"{len(problems)} problem(s):")
        for problem in problems:
            print(f"  {problem}")
        return 1

    print("theme files are consistent with the stylesheet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
