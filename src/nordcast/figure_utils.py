"""Small helpers shared by the scripts that draw nordcast's figures.

The style itself is `nordcast.paper_style`; this file holds only what is specific to
this repository: the provenance text every caption carries, and a way to keep end labels
from landing on top of each other.
"""

import itertools

# Energinet asks for attribution under CC BY 4.0 (notes/controls.md).
ATTRIBUTION = "Energinet, Energi Data Service"
LICENCE = "CC BY 4.0"


def label_offsets(ax, ys, gap_pt=9.0):
    """Vertical offsets in points that keep end labels at least `gap_pt` apart.

    `ys` are the data y values of the labels, in the order they will be drawn. Call it
    after the lines are plotted and `ps.frame` has set the margins, because the offsets
    are measured on the screen. Returns a list of offsets for `ps.end_label(..., dy=)`,
    each label moved as little as possible from its own line end (a simple one-pass
    spread from the middle outwards).
    """
    if not ys:
        return []
    ax.get_xlim(), ax.get_ylim()  # settle the lazy autoscale, or transData is stale
    fig = ax.figure
    scale = 72.0 / fig.dpi  # display pixels to points
    pos = [ax.transData.transform((0, y))[1] * scale for y in ys]
    order = sorted(range(len(pos)), key=lambda i: pos[i])
    placed = {i: pos[i] for i in order}
    for _ in range(50):
        moved = False
        for a, b in itertools.pairwise(order):
            gap = placed[b] - placed[a]
            if gap < gap_pt - 1e-9:
                push = (gap_pt - gap) / 2
                placed[a] -= push
                placed[b] += push
                moved = True
        if not moved:
            break
    return [placed[i] - pos[i] for i in range(len(ys))]


def name_label(ax, x, y, text, *, color, dy=0):
    """A direct label at the end of a line, with no value (`ps.end_label` always adds one).

    Same look as `ps.end_label`: 7.5 pt, in the line's colour, 6 points right of the end,
    shifted `dy` points up. `text` may hold a line break.
    """
    ax.annotate(
        text,
        (x, y),
        xytext=(6, dy),
        textcoords="offset points",
        va="center",
        ha="left",
        fontsize=7.5,
        color=color,
        annotation_clip=False,
    )
