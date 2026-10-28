#!/usr/bin/env node
/** Audit the generated site without fetching remote resources or adding dependencies. */
import { readFile, readdir, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const dist = path.join(root, 'dist');
const base = `/${(process.env.BASE_PATH || '/').replace(/^\/+|\/+$/g, '')}`;
const prefix = base === '/' ? '' : base;
const origin = new URL(process.env.SITE_URL || 'http://localhost:4321').origin;
const requiredRoutes = [
  '', 'intro', 'unix', 'gmt6-1', 'gmt6-2', 'obspy-1', 'obspy-2',
  'sta_lta', 'abs_loc', 'gcap', 'fk', 'eqt', 'dd_loc', 'source_spectra',
  'pylith_static', 'pylith_dynamic', 'body_tomo', 'surface_tomo',
  'ambient_tomo', 'appendix', 'intro/git-update', 'gmt6',
];
const errors = new Set();
const directoryCache = new Map();
const htmlCache = new Map();
const counts = { html: 0, contentPages: 0, localLinks: 0, localImages: 0, localResources: 0, anchors: 0 };

function decodeEntities(text) {
  const entities = { amp: '&', quot: '"', apos: "'", lt: '<', gt: '>', nbsp: '\u00a0' };
  return text.replace(/&(#x[\da-f]+|#\d+|amp|quot|apos|lt|gt|nbsp);/gi, (all, entity) => {
    if (entity[0] !== '#') return entities[entity.toLowerCase()] ?? all;
    const value = entity[1].toLowerCase() === 'x' ? parseInt(entity.slice(2), 16) : parseInt(entity.slice(1), 10);
    return value >= 0 && value <= 0x10ffff ? String.fromCodePoint(value) : all;
  });
}

function tags(html) {
  const clean = html.replace(/<!--[\s\S]*?-->/g, '').replace(/<(script|style)\b([^>]*)>[\s\S]*?<\/\1\s*>/gi, '<$1$2></$1>');
  return [...clean.matchAll(/<([a-z][\w:-]*)\b(?:[^"'>]|"[^"]*"|'[^']*')*>/gi)].map(match => {
    const attributes = {};
    for (const attribute of match[0].matchAll(/\s([^\s=/>]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/g)) {
      attributes[attribute[1].toLowerCase()] = decodeEntities(attribute[2] ?? attribute[3] ?? attribute[4]);
    }
    return { name: match[1].toLowerCase(), attributes };
  });
}

function srcsetUrls(value) {
  // Follow the URL/descriptor split, keeping commas inside data URLs intact.
  const urls = [];
  let index = 0;
  while (index < value.length) {
    while (/[\s,]/.test(value[index] || '') && index < value.length) index++;
    const start = index;
    while (index < value.length && !/\s/.test(value[index])) index++;
    let url = value.slice(start, index);
    if (!url) break;
    if (url.endsWith(',')) {
      urls.push(url.replace(/,+$/, ''));
      continue;
    }
    urls.push(url);
    while (index < value.length && value[index] !== ',') index++;
    if (index < value.length) index++;
  }
  return urls;
}

async function exactExists(filename) {
  const relative = path.relative(dist, filename);
  if (relative.startsWith('..') || path.isAbsolute(relative)) return false;
  let current = dist;
  for (const segment of relative.split(path.sep).filter(Boolean)) {
    let entries = directoryCache.get(current);
    if (!entries) {
      try { entries = new Set(await readdir(current)); } catch { return false; }
      directoryCache.set(current, entries);
    }
    if (!entries.has(segment)) return false;
    current = path.join(current, segment);
  }
  return true;
}

async function resolveFile(pathname) {
  let decoded;
  try { decoded = decodeURIComponent(pathname); } catch { return null; }
  const filename = path.resolve(dist, `.${decoded}`);
  if (!await exactExists(filename)) return null;
  if ((await stat(filename)).isDirectory()) {
    const index = path.join(filename, 'index.html');
    return await exactExists(index) ? index : null;
  }
  return filename;
}

async function getHtml(filename) {
  if (!htmlCache.has(filename)) {
    const html = await readFile(filename, 'utf8');
    const elements = tags(html);
    const anchors = new Set(elements.flatMap(({ name, attributes }) => [attributes.id, name === 'a' ? attributes.name : null]).filter(Boolean));
    htmlCache.set(filename, { html, elements, anchors });
  }
  return htmlCache.get(filename);
}

async function verifyUrl(value, filename, attribute, image) {
  if (!value || /^(?:data:|blob:|mailto:|tel:|javascript:)/i.test(value)) return;
  const relative = path.relative(dist, filename).split(path.sep).join('/');
  const pagePath = `${prefix}/${relative.replace(/index\.html$/, '')}`;
  let url;
  try { url = new URL(value, origin + pagePath); } catch {
    errors.add(`${relative}: invalid ${attribute} ${JSON.stringify(value)}`);
    return;
  }
  if (!['http:', 'https:'].includes(url.protocol) || url.origin !== origin) return;
  if (prefix && url.pathname !== prefix && !url.pathname.startsWith(prefix + '/')) {
    errors.add(`${relative}: ${attribute} misses BASE_PATH=${prefix}: ${value}`);
    return;
  }
  const pathname = url.pathname.slice(prefix.length) || '/';
  const target = await resolveFile(pathname);
  if (attribute === 'href') counts.localLinks++;
  else if (image) counts.localImages++;
  else counts.localResources++;
  if (!target) {
    errors.add(`${relative}: missing ${attribute} target ${value}`);
    return;
  }
  if (url.hash && path.extname(target).toLowerCase() === '.html') {
    let fragment;
    try { fragment = decodeURIComponent(url.hash.slice(1).split(':~:')[0]); } catch {
      errors.add(`${relative}: invalid fragment ${value}`);
      return;
    }
    if (fragment) {
      counts.anchors++;
      if (!(await getHtml(target)).anchors.has(fragment)) errors.add(`${relative}: missing anchor ${value}`);
    }
  }
}

async function htmlFiles(directory) {
  const files = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const filename = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await htmlFiles(filename));
    else if (entry.isFile() && entry.name.endsWith('.html')) files.push(filename);
  }
  return files;
}

async function main() {
  try { await stat(dist); } catch {
    console.error('Build output is missing. Run npm run build first.');
    process.exitCode = 1;
    return;
  }
  for (const route of requiredRoutes) {
    if (await exactExists(path.join(dist, route, 'index.html'))) counts.contentPages++;
    else errors.add(`Missing required content page: /${route}${route ? '/' : ''}`);
  }
  const files = await htmlFiles(dist);
  counts.html = files.length;
  for (const filename of files) {
    const relative = path.relative(dist, filename);
    const { html, elements } = await getHtml(filename);
    if (elements.some(({ attributes }) => (attributes.class || '').split(/\s+/).includes('katex-error'))) {
      errors.add(`${relative}: KaTeX failed to render at least one formula`);
    }
    const visibleText = decodeEntities(html
      .replace(/<!--[\s\S]*?-->/g, '')
      .replace(/<(pre|code|script|style|annotation)\b[^>]*>[\s\S]*?<\/\1\s*>/gi, '')
      .replace(/<[^>]+>/g, '\n'));
    const leftovers = visibleText.match(/\.\.[ \t]+(?:image|figure|math|code(?:-block)?|parsed-literal|note|tip|warning|toctree|rubric|centered|hlist)[ \t]*::|:(?:math|download|file):/gi);
    if (leftovers) errors.add(`${relative}: unconverted RST: ${[...new Set(leftovers)].join(', ')}`);
    for (const { name, attributes } of elements) {
      for (const attribute of ['href', 'src']) {
        // A 404 document's canonical URL is an identity, not a navigable route.
        if (name === 'link' && attribute === 'href' && (attributes.rel || '').split(/\s+/).includes('canonical')) continue;
        if (attributes[attribute] !== undefined) await verifyUrl(attributes[attribute], filename, attribute, name === 'img' || name === 'source');
      }
      if (attributes.srcset) {
        for (const url of srcsetUrls(attributes.srcset)) await verifyUrl(url, filename, 'srcset', true);
      }
    }
  }
  console.log(`Checked ${counts.html} HTML files; ${counts.contentPages}/${requiredRoutes.length} required content pages.`);
  console.log(`Checked ${counts.localLinks} local links, ${counts.localImages} local image references, ${counts.localResources} other resources, and ${counts.anchors} anchors.`);
  console.log(`Base path: ${prefix || '/'}. Remote URLs were preserved and not fetched.`);
  if (errors.size) {
    console.error(`\nVerification failed (${errors.size} issues):`);
    for (const error of errors) console.error(`- ${error}`);
    process.exitCode = 1;
  } else console.log('Build verification passed.');
}

await main();
