"""cardCircle() previously rendered <article class="reddit-card"> with only a
single .post-body child, but .reddit-card's CSS is a 2-column grid
(54px vote-rail | wide post-body). With no first child to fill the 54px
column, grid auto-placement squeezed the entire card's content into it
instead of the wide column, wrapping every line word-by-word (the status
pill, "u/name", date, title, and description all rendered as a single
vertical stack of near-single-word lines). Circles have no vote-rail
concept at all, so the fix adds a circle-card modifier that forces a
single-column layout instead of giving circles a fake vote rail."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_circle_card_is_not_squeezed_into_the_vote_rail_column() -> None:
    js = read("sites/community/community.js")
    css = read("sites/community/community.css")
    assert 'class="reddit-card circle-card"' in js
    assert ".circle-card{grid-template-columns:minmax(0,1fr)" in css.replace(" ", "")
