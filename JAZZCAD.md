JazzCAD: TokyoNight, English, and a checker that says so
=======================================================

JazzCAD is FreeCAD with the look of one desktop rather than of an application
that happens to be installed next to another one. This first step is the part
that can be checked without building anything: the theme of the interface, the
language it starts in, and a script that reads both of them and says whether
they agree with the stylesheet.

What is here
------------

* `src/Gui/Stylesheets/parameters/JazzCAD TokyoNight.yaml` - the colours. The
  reference TokyoNight palette, the accents taken from the Markdown viewer of
  this workstation so the two applications read as one system.
* `Gui::JazzCadTheme` (`src/Gui/Application.h`) - the name of that file, in one
  place, because the preferences window and the style parameter manager are
  separate translation units and have to give the same answer.
* English is the language until a person chooses another, and the Russian
  switch in Preferences keeps working.
* `tools/check-jazzcad-theme.py` - reads the stylesheet and the theme files
  together and reports what does not add up.

The choice of colours
---------------------

TokyoNight is not applied by listing sixteen hex values. It is applied by naming
the palette and letting the theme engine derive the shades, the way the stock
themes do:

    PrimaryColorLighten4: "lighten(@PrimaryColor, 26)"

That is the reason a surface, a hover and a panel are related to the background
rather than merely near it: change `PrimaryColor` and twenty shades follow it.

Two decisions are worth naming.

The text is `#c0caf5`, not white. On this background white vibrates, and a
person reads a drawing for hours.

The corner radius is 2px, down from the stock 3px. At 6px the panels of the
property editor begin to look like buttons, and a CAD window is mostly panels.

The solver colours are the palette's own red, orange and cyan. They are the one
place where a colour carries meaning rather than decoration: a conflict, a
redundancy and a failure have to be told apart at a glance, and they are told
apart by hue. The one departure is `#ff9090` for a failed solve - a paler red,
so "the solver gave up" is visible without looking like the red of a conflict
that must be fixed.

Why a checker was written for a file of colours
-----------------------------------------------

FreeCAD evaluates the tokens of a stylesheet through an expression engine
(`Gui/StyleParameters/Parser.cpp`: lighten, darken, blend) and falls back through
three sources when a token is missing. A mistake in the YAML is therefore not
caught by the compiler, not caught by a failed build, and not caught by a test:
it is caught by the window looking wrong, which is the most expensive way to
find out.

`tools/check-jazzcad-theme.py` asks the three questions that actually bite:

1. does every token the stylesheet asks for have a value?
2. does every key the file defines get read, and do the expressions parse?
3. do the colours stay inside the palette?

Run it from the root of the tree:

    python tools/check-jazzcad-theme.py

It needs no FreeCAD, no Qt and no network, and exits non-zero when something is
wrong, so it can sit in a hook. It was checked by breaking the theme file on
purpose: an unknown colour function, a colour outside the palette and a token
the stylesheet wants are each reported by name.

A mistake in the checker itself was worth as much as the checker. It first read
`TextDisabledColor: "#ff0000"` as a key with an empty value, because it cut the
line at the first `#` - so it passed a file whose colours it had never read. And
it first reported `@3DViewBackgroundRefColor` as unused, because the pattern for
a token name could not begin with a digit. Both are the kind of defect that
makes a checker worse than no checker, so both are fixed and both are why the
script says out loud what it does not check.

What is not here yet
--------------------

* The navigation. TinkerCAD and Free Turntable are the target: a view that turns
  freely rather than snapping to axes. This lives in the 3D viewer and needs a
  build to touch.
* The toolbar icons, in one monochrome. The theme sets
  `StylesheetIconsColor` and points the stylesheet at the dark icon folder, but
  the icons themselves are drawings and are not done.
* The mesh-to-solid converter on the right-click menu of a body.

None of these are guessed at here. Each needs the program running before it can
be written, and a change written without running it is a change nobody has seen.

Checking
--------

    python tools/check-jazzcad-theme.py
    clang-format --dry-run --Werror src/Gui/Application.cpp src/Gui/Application.h \
        src/Gui/PreferencePages/DlgSettingsGeneral.cpp
    black --line-length 100 --check tools/check-jazzcad-theme.py

The colour choice was taken from `src/style.css` of the Markdown viewer on this
workstation, which is where the palette comes from.
