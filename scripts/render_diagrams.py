#!/usr/bin/env python3
"""Render every diagram with one shared house style (RC5 WP3).

The `.dot` sources carry structure only: nodes, labels, edges, shapes and
layout hints. Colour, font, dpi, pen widths, margins and spacing live here, in
`STYLE`, so the whole set is visually identical and a style change is one edit.

Usage:
    python3 scripts/render_diagrams.py            # render every source
    python3 scripts/render_diagrams.py --migrate  # strip style attrs from sources
    python3 scripts/render_diagrams.py NAME...    # render selected sources

Rendering caps the natural width so no PNG exceeds the structure checker's
2000 px rule and so the type size stays close across the set when the build
fits each figure to text width.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'assets/diagrams/src'
OUT = ROOT / 'assets/diagrams/rendered'

# --------------------------------------------------------------------------
# The house style. Every value below is used by the renderer and asserted by
# scripts/tests/test_diagrams.py; no `.dot` source sets any of them.
# --------------------------------------------------------------------------
STYLE = {
    # Type: one font, one size for nodes, edges and cluster labels.
    # WP2 may ship Selawik under publishing/fonts; switching is this one line
    # once that font is installed, and nothing else changes.
    'font': 'Liberation Sans',
    'fontsize': 11,
    'text': '#000000',
    # Monochrome: white behind two light greys, and one accent.
    'node_fill': '#f2f2f2',
    'node_border': '#444444',
    'diamond_fill': '#e6e6e6',
    'edge': '#333333',
    'cluster_border': '#9a9a9a',
    # One accent colour, used only when RC4 had exactly one effective teal
    # node. Groups of equally teal nodes stay neutral; no arbitrary first pick.
    'accent': '#0065b3',
    # Geometry.
    'dpi': 200,
    'penwidth': 1.0,
    'focal_penwidth': 1.8,
    'arrowsize': 0.7,
    'margin': '0.14,0.07',
    'nodesep': 0.3,
    'ranksep': 0.4,
    'pad': 0.15,
    # Width rules.
    'max_width_px': 2000,
    'target_width_px': 1700,
}

STYLE_KEYS = (
    'fontname', 'fontsize', 'fontcolor', 'fillcolor', 'color', 'penwidth',
    'margin', 'dpi', 'bgcolor', 'nodesep', 'ranksep', 'pad', 'arrowsize', 'size',
)
KEEP_IN_STATEMENT = {
    'label', 'shape', 'style', 'class', 'rankdir', 'constraint', 'dir',
    'arrowhead', 'xlabel', 'lhead', 'ltail', 'rank', 'newrank', 'compound',
    'ordering', 'labeljust', 'labelloc', 'peripheries', 'height', 'width',
}

HEADER = (
    'graph [fontname="{font}", fontsize={fontsize}, fontcolor="{text}", '
    'bgcolor="white", pad={pad}, nodesep={nodesep}, ranksep={ranksep}, dpi={dpi}];\n'
    ' node [fontname="{font}", fontsize={fontsize}, shape=box, style="rounded,filled", '
    'fillcolor="{node_fill}", color="{node_border}", fontcolor="{text}", '
    'penwidth={penwidth}, margin="{margin}"];\n'
    ' edge [fontname="{font}", fontsize={fontsize}, color="{edge}", '
    'fontcolor="{edge}", arrowsize={arrowsize}, penwidth={penwidth}];\n'
).format(**STYLE)

CLUSTER_STYLE = (
    'fontname="{font}"; fontsize={fontsize}; fontcolor="{text}"; '
    'color="{cluster_border}"; penwidth={penwidth}; style="rounded,dashed";'
).format(**STYLE)

ATTR = re.compile(r'(\w+)\s*=\s*("(?:[^"\\]|\\.)*"|[^,\]\s]+)')


def strip_attrs(statement: str) -> str:
    """Rebuild one `[...]` block from the attributes that are not style."""
    match = re.search(r'\[([^\]]*)\]', statement, re.S)
    if not match:
        return statement
    kept = [f'{k}={v}' for k, v in ATTR.findall(match.group(1)) if k not in STYLE_KEYS]
    inner = ('[' + ', '.join(kept) + ']') if kept else ''
    return statement[:match.start()] + inner + statement[match.end():]


def strip_style(text: str) -> str:
    """Remove every style attribute, keeping nodes, labels, edges and layout."""
    out = []
    for line in text.split('\n'):
        stripped = line.strip()
        if not stripped or stripped == '}':
            out.append(line)
            continue
        line = re.sub(r'\bgraph\s*\[[^\]]*\]\s*;?', lambda match: strip_attrs(match.group(0)), line)
        line = re.sub(r'\b(?:node|edge)\s*\[[^\]]*\]\s*;?', '', line)
        line = re.sub(r'\b(?:%s)\s*=\s*(?:"[^"]*"|[^;\s]+)\s*;?' % '|'.join(STYLE_KEYS),
                      '', line)
        cluster = re.match(r'^(\s*subgraph\s+cluster_\w+\s*\{)(.*)$', line)
        if cluster:
            kept = [f'{k}={v}' for k, v in ATTR.findall(cluster.group(2))
                    if k in {'label', 'labeljust', 'labelloc'}]
            line = cluster.group(1) + (' ' + '; '.join(kept) + ';' if kept else '')
        elif '[' in line:
            line = strip_attrs(line)
        out.append(line)
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(out))


NODE_DEF = re.compile(r'([A-Za-z_]\w*)\s*\[([^\]]*)\]')
TEAL = '#e6f2f1'


def teal_nodes_from_source(text: str):
    """Effective RC4 teal nodes, resolved by Graphviz itself.

    Graphviz applies ``node`` defaults in declaration order and within their
    scope, and an explicit node ``fillcolor`` overrides the current default.
    Using ``dot -Tjson`` avoids re-implementing that scoping and catches the
    amber anti-pattern in ``ch12-test-portfolio`` (which overrides the teal
    default) as well as later scoped defaults.
    """
    result = subprocess.run(['dot', '-Tjson'], input=text.encode(),
                            capture_output=True, check=True)
    graph = json.loads(result.stdout)
    teal = []
    for obj in graph.get('objects', []):
        name = obj.get('name')
        if not name or name.startswith('cluster_'):
            continue
        if str(obj.get('fillcolor', '')).lower() == TEAL:
            teal.append(name)
    return teal


def rc4_teal_nodes(path: Path):
    """Effective teal nodes from the rc.4 tag; None when the tag is unavailable."""
    relative = f'assets/diagrams/src/{path.name}'
    result = subprocess.run(['git', '-C', str(ROOT), 'show', f'v2.1.0-rc.4:{relative}'],
                            capture_output=True, text=True)
    if result.returncode != 0:
        return None
    return teal_nodes_from_source(result.stdout)


def set_focal_nodes(text: str, names) -> str:
    """Mark the single approved focal node, removing stale focal markers."""
    names = set(names or ())
    out = []
    for line in text.split('\n'):
        if '->' in line or line.strip().startswith(('subgraph', 'graph [', 'node [', 'edge [')):
            out.append(line)
            continue

        def mark(match):
            name, attrs = match.group(1), match.group(2)
            attrs = re.sub(r'\s*class="focal"\s*,?', ' ', attrs).strip()
            if name in names:
                attrs = 'class="focal", '+attrs if attrs else 'class="focal"'
            return f'{name} [{attrs}]'
        out.append(NODE_DEF.sub(mark, line))
    return '\n'.join(out)


def migrate() -> int:
    """One-off: mark the single RC4 teal node, then strip style from every source.

    The approved contract is one focal element. When RC4 highlighted several
    equally teal nodes, the migrated source keeps none of them focal rather
    than choosing the first by file order.
    """
    changed, missing, multi = 0, [], []
    for path in sorted(SRC.glob('*.dot')):
        original = path.read_text()
        teal = rc4_teal_nodes(path)
        if teal is None:
            missing.append(path.name)
            continue
        if len(teal) > 1:
            multi.append((path.name, len(teal)))
        focal = teal if len(teal) == 1 else []
        text = set_focal_nodes(strip_style(original), focal)
        if text != original:
            path.write_text(text)
            changed += 1
    print(f'MIGRATE: {changed} sources rewritten; {len(multi)} with multiple teal nodes (no focal)')
    if missing:
        print(f'MIGRATE: {len(missing)} sources skipped (v2.1.0-rc.4 unavailable)')
    return 0


def compose(source: str) -> str:
    """Prepend the shared header and apply the role-based overrides."""
    brace = source.index('{')
    head, rest = source[:brace + 1], source[brace + 1:]
    rest = re.sub(r'(subgraph\s+cluster_\w+\s*\{)', r'\1 ' + CLUSTER_STYLE, rest)

    def node(match: re.Match) -> str:
        raw = match.group(1)
        pairs = [(k, v) for k, v in ATTR.findall(raw) if k != 'class']
        if 'class="focal"' in raw:
            pairs += [('fillcolor', 'white'), ('color', f'"{STYLE["accent"]}"'),
                      ('penwidth', str(STYLE['focal_penwidth']))]
        if any(k == 'shape' and 'diamond' in v for k, v in pairs):
            pairs.append(('fillcolor', f'"{STYLE["diamond_fill"]}"'))
        return '[' + ', '.join(f'{k}={v}' for k, v in pairs) + ']'

    rest = re.sub(r'\[([^\]]*)\]', node, rest)
    return head + '\n ' + HEADER + rest


def png_width(path: Path) -> int:
    return struct.unpack('>I', path.read_bytes()[16:20])[0]


def add_phys(path: Path, dpi: int) -> None:
    """Insert a pHYs chunk so the PNG declares its 200 dpi resolution.

    Graphviz honours the `dpi` attribute when rasterising but writes no pHYs
    chunk. Without it, image consumers cannot tell a 1700 px render at 200 dpi
    from one at 96 dpi.
    """
    data = path.read_bytes()
    if b'pHYs' in data:
        return
    ppm = round(dpi / 0.0254)
    payload = struct.pack('>IIB', ppm, ppm, 1)
    chunk = struct.pack('>I', len(payload)) + b'pHYs' + payload
    chunk += struct.pack('>I', zlib.crc32(chunk[4:]) & 0xffffffff)
    # The signature (8) and IHDR chunk (25) precede the first ancillary chunk.
    path.write_bytes(data[:33] + chunk + data[33:])


def render(path: Path) -> int:
    text = compose(path.read_text())
    out = OUT / (path.stem + '.png')
    cap = STYLE['target_width_px'] / STYLE['dpi']
    subprocess.run(['dot', '-Tpng', f'-Gsize={cap:.2f},40', '-o', str(out)],
                   input=text.encode(), check=True)
    add_phys(out, STYLE['dpi'])
    return png_width(out)


MANIFEST = ROOT / 'assets/diagrams/render-manifest.json'


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def update_manifest(paths) -> None:
    """Record the styled source and PNG hashes plus the style parameters.

    The manifest is the portable freshness/integrity gate: it is independent
    of the local Graphviz/Cairo/font stack, unlike byte comparison with a fresh
    render. ``styled_source_sha256`` covers the exact DOT text Graphviz
    received, so a change to ``compose``, ``HEADER`` or ``CLUSTER_STYLE`` is as
    stale as a change to the source itself. A full render replaces the exact
    file set; a selective render keeps other entries and drops stale ones.
    """
    current = {path.stem for path in SRC.glob('*.dot')}
    data = {'version': 2, 'style': STYLE, 'diagrams': {}}
    if MANIFEST.exists():
        try:
            previous = json.loads(MANIFEST.read_text())
            data['diagrams'] = {name: entry for name, entry in previous.get('diagrams', {}).items()
                                if name in current}
        except (OSError, ValueError):
            pass
    selected = {path.stem for path in paths}
    for path in paths:
        png = OUT / f'{path.stem}.png'
        if not png.exists():
            raise SystemExit(f'missing render for {path.name}: {png}')
        data['diagrams'][path.stem] = {
            'source_sha256': _sha256(path),
            'styled_source_sha256': hashlib.sha256(
                compose(path.read_text()).encode()).hexdigest(),
            'png_sha256': _sha256(png),
        }
    # Full render: entries are exactly the current sources. Selective: keep the
    # other entries only if their source still exists (pruned above).
    if selected == current:
        data['diagrams'] = {name: data['diagrams'][name] for name in sorted(current)}
    MANIFEST.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def check_manifest() -> list[str]:
    """Check the exact source/render set, style and all three frozen hashes."""
    try:
        data = json.loads(MANIFEST.read_text())
        if data.get('version') != 2 or data.get('style') != STYLE:
            return ['manifest version or style differs']
        sources = {p.stem for p in SRC.glob('*.dot')}
        renders = {p.stem for p in OUT.glob('*.png')}
        if not sources or sources != renders or sources != set(data['diagrams']):
            return ['manifest/source/render file sets differ or are empty']
        errors = []
        for stem in sorted(sources):
            source = SRC / f'{stem}.dot'
            expected = {
                'source_sha256': _sha256(source),
                'styled_source_sha256': hashlib.sha256(compose(source.read_text()).encode()).hexdigest(),
                'png_sha256': _sha256(OUT / f'{stem}.png'),
            }
            if data['diagrams'][stem] != expected:
                errors.append(f'{stem}: source, composed source or PNG hash differs')
        return errors
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f'manifest unavailable or invalid: {exc}']


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('names', nargs='*', help='source stems (default: all)')
    parser.add_argument('--migrate', action='store_true', help='strip style from sources')
    parser.add_argument('--check', action='store_true', help='verify the frozen manifest without Graphviz or writes')
    args = parser.parse_args()
    if args.check:
        if args.names or args.migrate:
            parser.error('--check cannot be combined with names or --migrate')
        errors = check_manifest()
        if errors:
            print('\n'.join(errors), file=sys.stderr)
            return 1
        print(f'DIAGRAMS_OK: {len(list(SRC.glob("*.dot")))} source/render pairs; raw, styled and PNG hashes match')
        return 0
    if args.migrate:
        return migrate()
    paths = ([SRC / f'{n}.dot' for n in args.names]
             if args.names else sorted(SRC.glob('*.dot')))
    widths = sorted((render(p), p.name) for p in paths)
    update_manifest(paths)
    print(f'RENDER: {len(widths)} diagrams, width min {widths[0][0]} max {widths[-1][0]} px')
    return 0


if __name__ == '__main__':
    sys.exit(main())
