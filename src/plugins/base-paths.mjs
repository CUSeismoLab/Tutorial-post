/** Prefix local Markdown and MDX asset/link URLs for project-based GitHub Pages. */
export default function basePaths({ base = '/' } = {}) {
  const prefix = base.replace(/\/$/, '');
  const local = (value) => typeof value === 'string' && value.startsWith('/') && !value.startsWith('//');
  const rewrite = (value) => prefix && local(value) && value !== prefix && !value.startsWith(`${prefix}/`) ? `${prefix}${value}` : value;
  return (tree) => {
    function walk(node) {
      if (node.type === 'element') {
        for (const key of ['href', 'src', 'poster']) {
          if (node.properties?.[key]) node.properties[key] = rewrite(node.properties[key]);
        }
      }
      if (node.type === 'mdxJsxFlowElement' || node.type === 'mdxJsxTextElement') {
        for (const attribute of node.attributes ?? []) {
          if (['href', 'src', 'poster'].includes(attribute.name)) attribute.value = rewrite(attribute.value);
        }
      }
      for (const child of node.children ?? []) walk(child);
    }
    walk(tree);
  };
}
