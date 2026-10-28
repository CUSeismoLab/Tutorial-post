#!/usr/bin/env python3
"""Convert CUSeisTut's Sphinx chapters to editable MDX via Pandoc's RST AST.

Requires Pandoc (or pypandoc_binary in the Python environment). Does not mutate
source files. Unknown AST nodes fail loudly; conversion counts and original RST
parser warnings are written to migration-report.json for review.
"""
from __future__ import annotations
import argparse
from collections import Counter
import html
import json
from pathlib import Path
import re
import shutil
import subprocess
import textwrap
import unicodedata
from urllib.parse import quote, unquote, urlsplit, urlunsplit

SOURCE_DEFAULT = Path(__file__).resolve().parents[3] / 'cuseistut/docs/source'
PROJECT = Path(__file__).resolve().parents[1]


def pandoc_path():
    installed = shutil.which('pandoc')
    if installed:
        return installed
    try:
        import pypandoc
        return pypandoc.get_pandoc_path()
    except ImportError as exc:
        raise SystemExit('Install Pandoc, or run this with a Python environment containing pypandoc_binary.') from exc


def normalize_rst(source: str, relative: str):
    """Repair narrowly identified RST syntax defects without touching originals."""
    # Whitespace-only tab lines confuse Pandoc's directive body indentation.
    source = re.sub(r'^[ \t]+$', '', source, flags=re.M).expandtabs(8)
    changes = ['Normalized whitespace-only lines before parsing to preserve code bodies.']
    normalized = re.sub(r'^(\s*\.\.\s+)(code|code-block|note|tip|warning|image|figure|centered|math)\s*::',
        lambda m: m[1] + m[2].lower() + '::', source, flags=re.M | re.I)
    if normalized != source:
        changes.append('Normalized directive capitalization/spacing (including code ::).')
    source = normalized
    source = re.sub(r'^(\s*\.\. (?:note|tip|warning)::)[ \t]*\n([ \t]*\|)', r'\1\n\n\2', source, flags=re.M)
    source = re.sub(r':math:[ \t]+`', ':math:`', source)
    # Parsed-literal is terminal output in this collection. Preserve its exact
    # line breaks and whitespace instead of allowing RST to parse it as prose.
    source = re.sub(r'^(\s*)\.\. parsed-literal::', r'\1.. code:: text', source, flags=re.M)
    # Several FK headings have adornments shorter than their text. Pandoc would
    # otherwise interpret them as one-column tables.
    lines = source.splitlines()
    for i in range(len(lines) - 2):
        if (re.fullmatch(r'([=#*+~-])\1{2,}', lines[i]) and lines[i + 1].strip()
            and re.fullmatch(re.escape(lines[i][0]) + r'{3,}', lines[i + 2])):
            width = max(len(lines[i]), len(lines[i + 1]), len(lines[i + 2]))
            if len(lines[i]) != width or len(lines[i + 2]) != width:
                changes.append(f'Extended short heading adornments for {lines[i+1]!r}.')
                lines[i] = lines[i][0] * width
                lines[i + 2] = lines[i + 2][0] * width
    for i in range(1, len(lines)):
        if (re.fullmatch(r'([=#*+~^\-])\1{2,}\s*', lines[i]) and lines[i - 1].strip()
            and not lines[i - 1][0].isspace()
            and not re.fullmatch(r'([=#*+~^\-])\1{2,}\s*', lines[i - 1])
            and not lines[i - 1].startswith('.. ')
            and len(lines[i - 1]) > len(lines[i].rstrip())):
            changes.append(f'Extended short underline for {lines[i-1]!r}.')
            lines[i] = lines[i][0] * len(lines[i - 1])
    source = '\n'.join(lines) + '\n'
    if relative == 'body_tomo/index.rst':
        source = re.sub(r'^#{50,}\n(?=``addEve0)', '----\n\n', source, flags=re.M)
        changes.append('Restored a separator before the addEve0.awk explanation.')
    if relative == 'dd_loc/index.rst':
        source = source.replace('### Damping the kernel Before damping:', 'Damping the kernel\n******************\n\nBefore damping:')
        source = source.replace('### Mathematical Meaning Write new constraints in equation, that is:', 'Mathematical Meaning\n********************\n\nWrite new constraints in equation, that is:')
        source = source.replace('(20 points) #### Hint The dimension', '(20 points)\n\n      **Hint:** The dimension')
        changes.append('Converted three embedded Markdown heading/hint markers to RST structure.')
    if relative == 'abs_loc/index.rst':
        source = source.replace(r'($\sigma$)', r'(:math:`\sigma`)')
        changes.append('Recovered a dollar-delimited sigma equation and a spaced math role.')
        source = re.sub(r'Why\?\n\.\. note::\s*\n\| Check', 'Why?\n\n.. note::\n\n   | Check', source)
        changes.append('Restored indentation of the covariance-matrix note.')
    if relative == 'obspy-1/index.rst':
        # A station data row contains adjacent | characters, which RST otherwise
        # mistakes for substitutions. Treat these two data lines as literals.
        source = re.sub(r'^( \| )(Network \|.*|YS\|BAOP.*)$',
                        lambda m: m[1] + '``' + m[2] + '``', source, flags=re.M)
        changes.append('Preserved pipe-delimited station metadata as literal text.')
    return source, changes


def text_content(nodes):
    result = []
    for n in nodes:
        t, c = n['t'], n.get('c')
        if t == 'Str': result.append(c)
        elif t in ('Space', 'SoftBreak', 'LineBreak'): result.append(' ')
        elif t in ('Code', 'Math'): result.append(c[1])
        elif t in ('Link', 'Image'): result.append(text_content(c[1]))
        elif t == 'Span': result.append(text_content(c[1]))
        elif isinstance(c, list): result.append(text_content(c))
        else: raise ValueError(f'Unsupported text node: {n}')
    return ''.join(result)


def normalize_math(value):
    # Unicode mathematical italic letters came from pasted equations; use
    # equivalent TeX symbols so KaTeX does not depend on fallback glyphs.
    value = unicodedata.normalize('NFKD', value)
    for char, command in {'τ': r'\tau ', '∫': r'\int ', '𝑑': 'd'}.items():
        value = value.replace(char, command)
    return value


def escape_text(value):
    # HTML character references avoid both JSX tags/expressions and accidental
    # Markdown constructs while keeping the rendered source text unchanged.
    value = value.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    value = value.replace('\\', '\\\\')
    for char in ('*', '_', '`', '[', ']', '|', '#'):
        value = value.replace(char, '\\' + char)
    value = value.replace('{', '&#123;').replace('}', '&#125;')
    value = value.replace('$', '&#36;')
    return value


class Writer:
    def __init__(self, source_root, source_file):
        self.root = source_root
        self.source = source_file
        self.relative = source_file.relative_to(source_root).as_posix()
        self.counts = Counter()
        self.missing = []
        self.external_images = []
        self.notes = []
        self.uses_aside = False
        self.heading_ids = []

    def path(self, uri, media=False):
        parts = urlsplit(uri)
        if parts.scheme or parts.netloc:
            if parts.hostname == 'cuseistut.readthedocs.io':
                route = re.sub(r'^/(?:en/)?(?:latest|stable)/', '/', parts.path)
                route = re.sub(r'/index\.html$', '/', route)
                route = re.sub(r'\.html$', '/', route)
                if not route.endswith('/'): route += '/'
                return urlunsplit(('', '', route.lower(), parts.query, '' if parts.fragment == '/' else parts.fragment))
            return uri
        if uri.startswith('#'):
            return uri
        actual = (self.source.parent / unquote(parts.path)).resolve()
        if parts.path.startswith('/'):
            actual = (self.root / unquote(parts.path).lstrip('/')).resolve()
        if actual.suffix in ('.html', '.rst') or (not media and not actual.suffix):
            if actual.suffix == '.html': actual = actual.with_suffix('.rst')
            if not actual.suffix: actual = actual.with_suffix('.rst')
            if actual.exists():
                rel = actual.relative_to(self.root).with_suffix('').as_posix()
                route = re.sub(r'(^|/)index$', '', rel).rstrip('/').lower()
                return '/' + route + '/' + ('#' + parts.fragment if parts.fragment else '')
        try:
            rel = actual.relative_to(self.root).as_posix()
        except ValueError:
            raise ValueError(f'{self.relative}: link escapes source tree: {uri}')
        if not actual.exists():
            self.missing.append({'original': uri, 'expected_source': rel})
        return '/media/' + quote(rel, safe='/@:+') + ('#' + parts.fragment if parts.fragment else '')

    def inline(self, nodes):
        return ''.join(self.one_inline(n) for n in nodes)

    def one_inline(self, n):
        t, c = n['t'], n.get('c')
        if t == 'Str':
            # RST disallows nested inline markup, but old authors used math
            # inside bold text. Recover those intended math roles here.
            if ':math:`' in c:
                chunks = re.split(r'(:math:`[^`]+`)', c)
                self.counts['inline_math'] += sum(s.startswith(':math:`') for s in chunks)
                return ''.join('$' + normalize_math(s[7:-1]) + '$' if s.startswith(':math:`') else escape_text(s) for s in chunks)
            return escape_text(c)
        if t in ('Space', 'SoftBreak'): return ' '
        if t == 'LineBreak': return '<br />\n'
        if t == 'Emph': return '*' + self.inline(c) + '*'
        if t == 'Strong': return '**' + self.inline(c) + '**'
        if t == 'Strikeout': return '~~' + self.inline(c) + '~~'
        if t == 'Code':
            role = dict(c[0][2]).get('role')
            if role == 'download':
                self.counts['downloads'] += 1
                match = re.fullmatch(r'\s*(.*?)\s*<([^>]+)>\s*', c[1])
                label, uri = (match[1], match[2]) if match else (c[1], c[1])
                return '[' + escape_text(label) + '](' + self.path(uri, media=True) + ')'
            if role and role != 'file':
                raise ValueError(f'Unsupported role {role} in {self.relative}')
            ticks = '`' * (1 + max([len(x) for x in re.findall(r'`+', c[1])] or [0]))
            text = c[1].replace('\n', ' ')
            if text.startswith(('`', ' ')) or text.endswith(('`', ' ')): text = ' ' + text + ' '
            return ticks + text + ticks
        if t == 'Math':
            display = c[0]['t'] == 'DisplayMath'
            self.counts['display_math' if display else 'inline_math'] += 1
            equation = normalize_math(c[1])
            if equation != c[1]: self.notes.append('Normalized Unicode mathematical glyphs to equivalent TeX symbols.')
            return ('\n\n$$\n' + equation + '\n$$\n\n') if display else '$' + equation + '$'
        if t == 'Link':
            uri = self.path(c[2][0])
            self.counts['links'] += 1
            label = self.inline(c[1])
            return '[' + label + '](' + uri.replace(' ', '%20').replace('(', '%28').replace(')', '%29') + ')'
        if t == 'Image':
            self.counts['images'] += 1
            uri = self.path(c[2][0], media=True)
            if urlsplit(uri).scheme: self.external_images.append(uri)
            alt = text_content(c[1])
            if not alt or alt == 'image':
                alt = Path(unquote(urlsplit(c[2][0]).path)).stem.replace('_', ' ').replace('-', ' ')
            attributes = dict(c[0][2])
            width = attributes.get('width')
            style = (' style={{width: ' + json.dumps(width) + '}}') if width else ''
            return '<img src="' + html.escape(uri, quote=True) + '" alt="' + html.escape(alt, quote=True) + '"' + style + ' loading="lazy" />'
        if t == 'Span':
            return self.inline(c[1])
        if t in ('Superscript', 'Subscript'):
            tag = 'sup' if t == 'Superscript' else 'sub'
            return f'<{tag}>' + self.inline(c) + f'</{tag}>'
        if t == 'Quoted': return '“' + self.inline(c[1]) + '”'
        raise ValueError(f'Unsupported inline node {t} in {self.relative}: {n}')

    def blocks(self, blocks):
        return '\n\n'.join(self.block(n).strip('\n') for n in blocks if n).strip('\n')

    def list_item(self, blocks, prefix):
        text = self.blocks(blocks)
        lines = text.splitlines()
        return prefix + lines[0] + '\n' + '\n'.join((' ' * len(prefix) + line) if line else '' for line in lines[1:]) if lines else prefix

    def block(self, n):
        t, c = n['t'], n.get('c')
        if t in ('Para', 'Plain'): return self.inline(c)
        if t == 'Header':
            self.counts['headings'] += 1
            self.heading_ids.append({'id': c[1][0], 'text': text_content(c[2])})
            return '#' * min(c[0], 6) + ' ' + self.inline(c[2])
        if t == 'CodeBlock':
            if not c[1].strip():
                raise ValueError(f'Empty code block in {self.relative}; inspect the RST directive indentation.')
            self.counts['code_blocks'] += 1
            languages = [s for s in c[0][1] if s]
            language = languages[0] if languages else 'text'
            # Original directives rarely declare a language. Infer only when
            # syntax is unambiguous; preserve mixed console transcripts as text.
            if language == 'text' and not languages:
                body = c[1]
                if re.search(r'^(from \w.* import|import (?:numpy|obspy|matplotlib)|def \w+\()', body, re.M): language = 'python'
                elif body.startswith('#!/bin/'): language = 'bash'
                elif self.source.parent.name == 'source_spectra': language = 'matlab'
            fence = '`' * max(3, 1 + max([len(x) for x in re.findall(r'`+', c[1])] or [0]))
            return fence + language + '\n' + c[1] + '\n' + fence
        if t == 'LineBlock': return '<br />\n'.join(self.inline(line) for line in c)
        if t == 'HorizontalRule': return '---'
        if t == 'BlockQuote' and len(c) == 1 and c[0]['t'] == 'Table': return self.blocks(c)
        if t == 'BlockQuote': return '\n'.join('> ' + line if line else '>' for line in self.blocks(c).splitlines())
        if t == 'BulletList': return '\n\n'.join(self.list_item(item, '- ') for item in c)
        if t == 'OrderedList':
            start = c[0][0]
            return '\n\n'.join(self.list_item(item, f'{start+i}. ') for i, item in enumerate(c[1]))
        if t == 'DefinitionList':
            return '\n\n'.join('**' + self.inline(term) + '**\n\n' + self.blocks([{'t':'BlockQuote','c':definition} for definition in defs]) for term, defs in c)
        if t == 'Div':
            attr, blocks = c
            classes = attr[1]
            aside_types = {'note':'note', 'tip':'tip', 'warning':'caution', 'caution':'caution', 'important':'note', 'danger':'danger'}
            kind = next((s for s in classes if s in aside_types), None)
            if kind:
                self.uses_aside = True
                self.counts['admonitions'] += 1
                if blocks and blocks[0]['t'] == 'Div' and 'title' in blocks[0]['c'][0][1]: blocks = blocks[1:]
                return f'<Aside type="{aside_types[kind]}">\n\n{self.blocks(blocks)}\n\n</Aside>'
            if 'centered' in classes:
                return '<div className="legacy-centered">\n\n' + self.blocks(blocks) + '\n\n</div>'
            if 'toctree' in classes:
                refs = []
                for block in blocks:
                    if block['t'] not in ('Para', 'Plain'): raise ValueError('Unsupported toctree contents')
                    for ref in text_content(block['c']).split():
                        target = (self.source.parent / (ref + '.rst'))
                        title = target.read_text().splitlines()[0] if target.exists() else ref
                        refs.append('- [' + escape_text(title) + '](' + self.path(ref) + ')')
                return '\n'.join(refs)
            if not classes: return self.blocks(blocks)
            raise ValueError(f'Unsupported Div classes {classes} in {self.relative}')
        if t == 'Table': return self.table(c)
        if t == 'Figure':
            return self.blocks(c[2]) + ('\n\n' + self.blocks(c[1][1]) if c[1][1] else '')
        raise ValueError(f'Unsupported block node {t} in {self.relative}: {n}')

    def table(self, c):
        self.counts['tables'] += 1
        _, caption, columns, head, bodies, foot = c
        def cells(row):
            result = []
            for cell in row[1]:
                if cell[2:4] != [1, 1]: raise ValueError('Row/column spans require manual migration')
                result.append(self.blocks(cell[4]).replace('\n', '<br />').replace('|','\\|'))
            return result
        headers = [cells(row) for row in head[1]]
        data = []
        for body in bodies: data.extend(cells(row) for row in body[2] + body[3])
        data.extend(cells(row) for row in foot[1])
        if len(headers) > 1: raise ValueError('Multiple table header rows require manual migration')
        header = headers[0] if headers else [''] * len(columns)
        rows = [header, ['---'] * len(columns)] + data
        result = '\n'.join('| ' + ' | '.join(row) + ' |' for row in rows)
        return (self.blocks(caption[1]) + '\n\n' if caption[1] else '') + result


def walk_counts(value, counts=None):
    if counts is None: counts = Counter()
    if isinstance(value, dict):
        if 't' in value: counts[value['t']] += 1
        for sub in value.values(): walk_counts(sub, counts)
    elif isinstance(value, list):
        for sub in value: walk_counts(sub, counts)
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE_DEFAULT)
    parser.add_argument('--output', type=Path, default=PROJECT / 'src/content/docs')
    args = parser.parse_args()
    root = args.source.resolve()
    report = {'source': str(root), 'converter': 'Pandoc RST AST with explicit MDX writer', 'pages': [], 'totals': {}}
    totals = Counter()
    for source in sorted(root.rglob('*.rst')):
        if source == root / 'index.rst': continue
        relative = source.relative_to(root)
        rst, repairs = normalize_rst(source.read_text(), relative.as_posix())
        proc = subprocess.run([pandoc_path(), '-f', 'rst', '-t', 'json'], input=rst, capture_output=True, text=True, check=True)
        ast = json.loads(proc.stdout)
        ast_counts = walk_counts(ast)
        writer = Writer(root, source)
        blocks = ast['blocks']
        if not blocks or blocks[0]['t'] != 'Header': raise ValueError(f'Missing title: {relative}')
        title = text_content(blocks[0]['c'][2]).strip()
        slug = relative.with_suffix('').as_posix().lower()
        slug = re.sub(r'/index$', '', slug)
        body = writer.blocks(blocks[1:])
        if writer.uses_aside:
            body = "import { Aside } from '@astrojs/starlight/components';\n\n" + body
        content = '---\ntitle: ' + json.dumps(title, ensure_ascii=False) + '\nslug: ' + slug + '\n---\n\n' + body + '\n'
        destination = args.output / relative.with_suffix('.mdx')
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content)
        # Ensure all syntax categories that can silently disappear during parsing
        # preserve their source count before a successful conversion is reported.
        expected = {
            'code_blocks': len(re.findall(r'^\s*\.\.\s+(?:code|code-block|parsed-literal)\s*::', source.read_text(), re.M | re.I)),
            'images': len(re.findall(r'^\s*\.\.\s+(?:image|figure)\s*::', source.read_text(), re.M | re.I)),
            'display_math': len(re.findall(r'^\s*\.\.\s+math\s*::', source.read_text(), re.M | re.I)),
            'admonitions': len(re.findall(r'^\s*\.\.\s+(?:note|tip|warning)\s*::', source.read_text(), re.M | re.I)),
            'downloads': len(re.findall(r':download:`', source.read_text())),
        }
        mismatches = {key: {'source': count, 'output': writer.counts[key]} for key, count in expected.items() if writer.counts[key] != count}
        if mismatches: raise ValueError(f'Content count mismatch in {relative}: {mismatches}')
        totals.update(writer.counts)
        report['pages'].append({'source': relative.as_posix(), 'target': str(destination.relative_to(PROJECT)), 'slug': slug, 'title': title,
            'counts': dict(writer.counts), 'expected_counts': expected, 'repairs': repairs + list(dict.fromkeys(writer.notes)),
            'parser_warnings': proc.stderr.strip(), 'missing_assets': writer.missing,
            'external_images': writer.external_images, 'headings': writer.heading_ids})
        print(f'{relative}: {sum(writer.counts.values())} content elements')
    report['totals'] = dict(totals)
    report['totals']['pages'] = len(report['pages'])
    (PROJECT / 'migration-report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(report['totals'], indent=2))

if __name__ == '__main__':
    main()
