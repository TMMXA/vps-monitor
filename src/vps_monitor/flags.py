from __future__ import annotations


def _us_stars() -> str:
    rows = []
    for row in range(5):
        for col in range(6):
            rows.append(f'<circle cx="{4 + col * 4.1:.1f}" cy="{4 + row * 5.6:.1f}" r="0.7" fill="#fff"/>')
    for row in range(4):
        for col in range(5):
            rows.append(f'<circle cx="{6 + col * 4.1:.1f}" cy="{6.8 + row * 5.6:.1f}" r="0.7" fill="#fff"/>')
    return "".join(rows)


def _us_flag() -> str:
    stripes = []
    stripe_h = 72 / 13
    for index in range(13):
        color = "#b22234" if index % 2 == 0 else "#fff"
        stripes.append(f'<rect y="{index * stripe_h:.2f}" width="72" height="{stripe_h:.2f}" fill="{color}"/>')
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 72 72">'
        '<clipPath id="r"><rect width="72" height="72" rx="8"/></clipPath>'
        '<g clip-path="url(#r)">'
        f'{"".join(stripes)}'
        '<rect width="31" height="39" fill="#3c3b6e"/>'
        f'{_us_stars()}'
        '</g></svg>'
    )


FLAG_SVGS = {
    "mo": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 72 72">'
        '<clipPath id="r"><rect width="72" height="72" rx="8"/></clipPath>'
        '<g clip-path="url(#r)">'
        '<rect width="72" height="72" fill="#067a46"/>'
        '<path d="M36 21l1.7 5.1h5.4l-4.4 3.2 1.7 5.1-4.4-3.2-4.4 3.2 1.7-5.1-4.4-3.2h5.4z" fill="#ffde00"/>'
        '<path d="M19 18l.8 2.4h2.5l-2 1.5.8 2.4-2.1-1.5-2 1.5.8-2.4-2.1-1.5h2.6z" fill="#ffde00"/>'
        '<path d="M53 18l.8 2.4h2.5l-2 1.5.8 2.4-2.1-1.5-2 1.5.8-2.4-2.1-1.5h2.6z" fill="#ffde00"/>'
        '<path d="M24 39c5-12 19-12 24 0-7-5-17-5-24 0z" fill="#fff"/>'
        '<path d="M28 42c5-5 11-5 16 0-5 2-11 2-16 0z" fill="#fff"/>'
        '<path d="M20 49h32M24 55h24" stroke="#fff" stroke-width="3" stroke-linecap="round"/>'
        '</g></svg>'
    ),
    "us": _us_flag(),
    "unknown": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 72 72">'
        '<rect width="72" height="72" rx="8" fill="#f8fafc"/>'
        '<path d="M23 16v42" stroke="#64748b" stroke-width="4" stroke-linecap="round"/>'
        '<path d="M25 17h30v23H25z" fill="#e2e8f0" stroke="#94a3b8" stroke-width="2"/>'
        '</svg>'
    ),
}
