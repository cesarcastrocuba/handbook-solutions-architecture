"""Guards for the RC5 WP3 diagram style contract.

The style itself lives in `scripts/render_diagrams.py` (`STYLE`); these tests
keep it there: no `.dot` source may carry a font, colour, dpi, pen width or
spacing attribute, the single approved focal node (only when RC4 had exactly
one effective teal node), every source must have a rendered PNG and vice
versa, every PNG must be at most 2000 px wide and declare 200 dpi, and a
tracked manifest binds the raw source, the composed (styled) source and the
PNG. The retained legacy sizing tests require the intentionally unported build module;
they do not verify the platform edition. In the legacy build, effective printed type is measured
with its own figure rule, so
every diagram must stay at 10 pt or more after both the Graphviz size clamp and
the build's width/tall-page caps, and no figure may be enlarged past its
natural width.
"""
from __future__ import annotations

import re
import struct
import subprocess
import sys
import tempfile
import json
import os
import unittest
import hashlib
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))

import importlib.util
from unittest import mock

HAS_DOT = shutil.which("dot") is not None
HAS_RC4 = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--verify", "v2.1.0-rc.4"], capture_output=True).returncode == 0
HAS_LEGACY_BUILD = importlib.util.find_spec("build_book") is not None
import render_diagrams  # noqa: E402

SRC = ROOT / 'assets/diagrams/src'
OUT = ROOT / 'assets/diagrams/rendered'
STYLE_ATTR = re.compile(
    r'\b(fontname|fontsize|fontcolor|fillcolor|color|penwidth|margin|dpi|bgcolor|'
    r'nodesep|ranksep|pad|arrowsize|size)\s*=', re.I)
PHYS = b'pHYs'
FOCAL = re.compile(r'([A-Za-z_]\w*)\s*\[[^\]]*class="focal"')
# Sources added after v2.1.0-rc.4 have no RC4 colour to preserve, so they carry no accent.
POST_RC4_SOURCES = {
    'ch06-mediation-selection', 'ch06-mediation-topologies',
    'ch07-client-composition', 'ch07-tenancy-models',
    'ch04-team-interactions', 'ch08-runtime-selection', 'ch08-edge-iot-tiers',
    'ch16-agent-control-points', 'ch08-request-path',
    'ch12-docs-as-code', 'ch13-utility-tree', 'ch13-atam-phases', 'ch13-continuous-evaluation',
    'ch14-quality-verification-map', 'ch14-test-evidence-flow',
    'ch12-c4-levels',
    'platform-types', 'platform-product-loop', 'platform-responsibility', 'platform-reference-architecture',
    'platform-abstraction-levels', 'platform-isolation', 'platform-policy-lifecycle', 'platform-planes-failure',
    'platform-measures', 'platform-cost-flow', 'platform-sourcing',
}


def png_size(path: Path) -> tuple[int, int]:
    return struct.unpack('>II', path.read_bytes()[16:24])


def png_dpi(path: Path) -> int:
    """Horizontal resolution from the pHYs chunk, in dots per inch."""
    data = path.read_bytes()
    index = data.find(PHYS)
    if index == -1:
        return 0
    x_ppm = struct.unpack('>I', data[index + 4:index + 8])[0]
    return round(x_ppm * 0.0254)


def natural_sizes() -> dict[str, tuple[int, int]]:
    """Width and height at natural size: composed source, no width clamp."""
    sizes = {}
    with tempfile.TemporaryDirectory() as temporary:
        for path in sorted(SRC.glob('*.dot')):
            target = Path(temporary) / f'{path.stem}.png'
            subprocess.run(['dot', '-Tpng', '-Gsize=40,40', '-o', str(target)],
                           input=render_diagrams.compose(path.read_text()).encode(),
                           check=True)
            sizes[path.stem] = png_size(target)
    return sizes


class StyleTests(unittest.TestCase):
    def test_sources_carry_no_style_attributes(self):
        offenders = []
        for path in sorted(SRC.glob('*.dot')):
            for number, line in enumerate(path.read_text().split('\n'), 1):
                match = STYLE_ATTR.search(line)
                if match:
                    offenders.append(f'{path.name}:{number}: {match.group(0)}')
        self.assertEqual(offenders, [], 'style attributes belong in render_diagrams.STYLE')

    def test_style_constants_are_single_valued(self):
        style = render_diagrams.STYLE
        expected = {
            'font': 'Liberation Sans', 'fontsize': 11, 'text': '#000000',
            'node_fill': '#f2f2f2', 'node_border': '#444444',
            'diamond_fill': '#e6e6e6', 'edge': '#333333',
            'cluster_border': '#9a9a9a', 'accent': '#0065b3',
            'dpi': 200, 'penwidth': 1.0, 'focal_penwidth': 1.8,
            'arrowsize': 0.7, 'margin': '0.14,0.07', 'nodesep': 0.3,
            'ranksep': 0.4, 'pad': 0.15, 'max_width_px': 2000,
        }
        for key, value in expected.items():
            with self.subTest(key=key):
                self.assertEqual(style[key], value)
        header = render_diagrams.HEADER
        self.assertEqual(header.count(f'fontname="{style["font"]}"'), 3)
        self.assertEqual(header.count(f'fontsize={style["fontsize"]}'), 3)
        for fragment in (f'dpi={style["dpi"]}', f'fillcolor="{style["node_fill"]}"',
                         f'color="{style["node_border"]}"', f'penwidth={style["penwidth"]}',
                         f'arrowsize={style["arrowsize"]}', f'margin="{style["margin"]}"',
                         f'nodesep={style["nodesep"]}', f'ranksep={style["ranksep"]}',
                         f'pad={style["pad"]}'):
            self.assertIn(fragment, header)
        self.assertIn(f'color="{style["cluster_border"]}"', render_diagrams.CLUSTER_STYLE)
        self.assertIn(f'penwidth={style["penwidth"]}', render_diagrams.CLUSTER_STYLE)

    @unittest.skipUnless(HAS_DOT, "optional Graphviz parser audit")
    def test_teal_nodes_from_source_honours_scoped_defaults_and_overrides(self):
        """Parser evidence independent of migration: order, scope and explicit fills."""
        source = '''digraph G {
 a [label="a"];
 node [fillcolor="#E6F2F1"];
 b [label="b"];
 subgraph cluster_x {
   node [fillcolor="#FFF4E0"];
   c [label="c"];
   d [label="d", fillcolor="#E6F2F1"];
 }
 e [label="e"];
 f [label="f", fillcolor="#EEF3F8"];
}
'''
        self.assertEqual(set(render_diagrams.teal_nodes_from_source(source)), {'b', 'd', 'e'})

    @unittest.skipUnless(HAS_DOT and HAS_RC4, "legacy RC4 tag/Graphviz audit; frozen manifest is the portable gate")
    def test_focal_nodes_follow_the_single_focal_contract(self):
        """Only a single effective RC4 teal node may carry the accent."""
        for path in sorted(SRC.glob('*.dot')):
            if path.stem in POST_RC4_SOURCES:
                with self.subTest(path=path.name):
                    self.assertEqual(FOCAL.findall(path.read_text()), [])
                continue
            expected = render_diagrams.rc4_teal_nodes(path)
            self.assertIsNotNone(expected, f'{path.name}: v2.1.0-rc.4 evidence unavailable')
            focal = FOCAL.findall(path.read_text())
            expected_focal = expected if len(expected) == 1 else []
            with self.subTest(path=path.name):
                self.assertEqual(set(focal), set(expected_focal))

    @unittest.skipUnless(HAS_DOT and HAS_RC4, "legacy RC4 tag/Graphviz audit; frozen manifest is the portable gate")
    def test_test_portfolio_does_not_accent_the_amber_anti_pattern(self):
        """Hard-coded regression for the teal-default override in V2."""
        path = SRC / 'ch12-test-portfolio.dot'
        self.assertEqual(set(render_diagrams.rc4_teal_nodes(path)),
                         {'e2e', 'int', 'arch', 'unit'})
        text = path.read_text()
        self.assertEqual(FOCAL.findall(text), [])
        self.assertNotRegex(text, r'\binv\s*\[[^\]]*class="focal"')

    def test_sources_and_renders_pair_up(self):
        sources = {p.stem for p in SRC.glob('*.dot')}
        renders = {p.stem for p in OUT.glob('*.png')}
        self.assertEqual(sources - renders, set(), 'sources without a rendered PNG')
        self.assertEqual(renders - sources, set(), 'rendered PNGs without a source')


class RenderTests(unittest.TestCase):
    def test_widths_within_the_checker_limit(self):
        limit = render_diagrams.STYLE['max_width_px']
        for path in sorted(OUT.glob('*.png')):
            width, _ = png_size(path)
            with self.subTest(path=path.name):
                self.assertLessEqual(width, limit, f'{path.name} is {width}px wide')

    def test_every_png_declares_the_style_dpi(self):
        expected = render_diagrams.STYLE['dpi']
        for path in sorted(OUT.glob('*.png')):
            with self.subTest(path=path.name):
                self.assertEqual(png_dpi(path), expected, f'{path.name} has no {expected} dpi pHYs chunk')

    def test_manifest_binds_every_source_and_render(self):
        """Portable freshness gate: raw source, composed source, PNG, style, exact set."""
        manifest = json.loads(render_diagrams.MANIFEST.read_text())
        self.assertEqual(manifest['version'], 2)
        self.assertEqual(manifest['style'], render_diagrams.STYLE)
        sources = {path.stem for path in SRC.glob('*.dot')}
        renders = {path.stem for path in OUT.glob('*.png')}
        self.assertEqual(set(manifest['diagrams']), sources)
        self.assertEqual(renders, sources)
        for stem in sorted(sources):
            entry = manifest['diagrams'][stem]
            source = SRC / f'{stem}.dot'
            with self.subTest(path=stem):
                self.assertEqual(entry['source_sha256'],
                                 hashlib.sha256(source.read_bytes()).hexdigest())
                self.assertEqual(entry['styled_source_sha256'],
                                 hashlib.sha256(
                                     render_diagrams.compose(source.read_text()).encode()).hexdigest(),
                                 'rendered input changed without a new render')
                self.assertEqual(entry['png_sha256'],
                                 hashlib.sha256((OUT / f'{stem}.png').read_bytes()).hexdigest())

    @unittest.skipUnless(os.environ.get('DIAGRAM_RERENDER_AUDIT') == '1',
                         'local raster audit; cross-platform bytes are not a CI gate')
    def test_local_rerender_audit(self):
        """Optional environment-specific proof; the manifest is the portable gate."""
        with tempfile.TemporaryDirectory() as temporary:
            for path in sorted(SRC.glob('*.dot')):
                target = Path(temporary) / f'{path.stem}.png'
                subprocess.run(['dot', '-Tpng', '-Gsize=8.50,40', '-o', str(target)],
                               input=render_diagrams.compose(path.read_text()).encode(),
                               check=True)
                render_diagrams.add_phys(target, render_diagrams.STYLE['dpi'])
                committed = OUT / f'{path.stem}.png'
                with self.subTest(path=path.name):
                    self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(),
                                     hashlib.sha256(committed.read_bytes()).hexdigest(),
                                     f'{path.name} differs from the local rerender')

    def test_compose_injects_the_header_and_strips_nothing_else(self):
        text = (SRC / 'governance.dot').read_text()
        composed = render_diagrams.compose(text)
        self.assertIn(f'fontname="{render_diagrams.STYLE["font"]}"', composed)
        self.assertIn(f'dpi={render_diagrams.STYLE["dpi"]}', composed)
        self.assertEqual(sorted(re.findall(r'label="([^"]*)"', composed)),
                         sorted(re.findall(r'label="([^"]*)"', text)))
        expected_focal = FOCAL.findall(text)
        self.assertEqual(composed.count(render_diagrams.STYLE['accent']), len(expected_focal))

    def test_strip_style_keeps_graph_layout_and_labels(self):
        sample = 'digraph G { graph [rankdir=LR, label="Graph", bgcolor="white", pad=0.2]; a -> b; }'
        stripped = render_diagrams.strip_style(sample)
        self.assertIn('rankdir=LR', stripped)
        self.assertIn('label="Graph"', stripped)
        self.assertNotIn('bgcolor', stripped)
        self.assertNotIn('pad=', stripped)


@unittest.skipUnless(HAS_LEGACY_BUILD and HAS_DOT, "legacy build sizing belongs to the toolkit; build_book.py is deliberately not ported")
class EffectivePrintTests(unittest.TestCase):
    """Measure real printed type with the build's own figure rule."""

    @classmethod
    def setUpClass(cls):
        global build_book
        import build_book
        cls.natural = natural_sizes()
        cls.text_width = build_book.TEXT_WIDTH_IN
        cls.max_aspect = build_book.MAX_ASPECT
        cls.dpi = build_book.NATURAL_DPI
        cls.fontsize = render_diagrams.STYLE['fontsize']

    def printed(self, stem):
        pct = build_book._figure_width(str(OUT / f'{stem}.png'))
        natural_w, natural_h = self.natural[stem]
        printed_in = pct / 100 * self.text_width
        effective = self.fontsize * printed_in / (natural_w / self.dpi)
        return pct, natural_w, natural_h, printed_in, effective

    def test_every_diagram_prints_at_least_ten_points(self):
        """10 pt after the Graphviz clamp, the width cap and the tall-page cap."""
        for stem in sorted(self.natural):
            _, natural_w, _, printed_in, effective = self.printed(stem)
            with self.subTest(path=stem):
                self.assertGreaterEqual(
                    round(effective, 2), 10.0,
                    f'{stem}: {effective:.2f} pt on the printed page '
                    f'(natural {natural_w}px, printed {printed_in:.2f} in)')

    def test_figures_are_never_enlarged_past_their_natural_width(self):
        """No upscaling and no blanket 100%: narrow art prints narrow."""
        stretched = []
        for stem in sorted(self.natural):
            pct, natural_w, natural_h, printed_in, _ = self.printed(stem)
            natural_in = natural_w / self.dpi
            with self.subTest(path=stem):
                self.assertLessEqual(pct, 100, f'{stem}: figure asks for {pct}% of the column')
                self.assertLessEqual(printed_in, natural_in + 0.005,
                                     f'{stem}: printed {printed_in:.2f} in > natural {natural_in:.2f} in')
            if natural_in < self.text_width and pct == 100:
                stretched.append(stem)
        self.assertEqual(stretched, [], 'narrow diagrams must not be stretched to the text width')

class ManifestCheckTests(unittest.TestCase):
    def test_frozen_manifest_passes_without_graphviz_or_writes(self):
        before = render_diagrams.MANIFEST.read_bytes()
        with mock.patch.object(render_diagrams.subprocess, 'run', side_effect=AssertionError('must not render')):
            self.assertEqual(render_diagrams.check_manifest(), [])
        self.assertEqual(render_diagrams.MANIFEST.read_bytes(), before)

    def test_detects_source_render_style_and_file_set_changes(self):
        for mutation in ('source', 'render', 'style', 'composed', 'entry', 'extra', 'missing', 'invalid'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp);src = root/'src';out = root/'rendered'
                src.mkdir();out.mkdir();manifest = root/'manifest.json'
                source = src/'test.dot';png = out/'test.png'
                source.write_text('digraph G { a -> b; }\n');png.write_bytes(b'frozen image')
                with mock.patch.multiple(render_diagrams, SRC=src, OUT=out, MANIFEST=manifest):
                    render_diagrams.update_manifest([source])
                    self.assertEqual(render_diagrams.check_manifest(), [])
                    if mutation == 'source':source.write_text('digraph G { b -> a; }\n')
                    elif mutation == 'render':png.write_bytes(b'changed image')
                    elif mutation == 'style':
                        data = json.loads(manifest.read_text());data['style']['font'] = 'Changed';manifest.write_text(json.dumps(data))
                    elif mutation == 'composed':
                        data = json.loads(manifest.read_text());data['diagrams']['test']['styled_source_sha256'] = 'stale';manifest.write_text(json.dumps(data))
                    elif mutation == 'entry':
                        data = json.loads(manifest.read_text());data['diagrams'] = {};manifest.write_text(json.dumps(data))
                    elif mutation == 'extra':(out/'extra.png').write_bytes(b'extra')
                    elif mutation == 'missing':png.unlink()
                    elif mutation == 'invalid':manifest.write_text('{broken')
                    self.assertTrue(render_diagrams.check_manifest())


if __name__ == '__main__':
    unittest.main()
