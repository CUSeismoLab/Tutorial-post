import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import { unified } from '@astrojs/markdown-remark';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import basePaths from './src/plugins/base-paths.mjs';

const base = process.env.BASE_PATH || '/';

export default defineConfig({
  site: process.env.SITE_URL || 'http://localhost:4321',
  base,
  output: 'static',
  trailingSlash: 'always',
  markdown: {
    processor: unified({
      smartypants: false,
      remarkPlugins: [remarkMath],
      rehypePlugins: [[rehypeKatex, { strict: 'ignore' }], [basePaths, { base }]],
    }),
  },
  integrations: [
    starlight({
      title: 'CUHK Seismology LAB',
      description: 'Hands-on seismology tutorials from the CUHK Seismology Lab. Learn scientific computing, seismic data processing, earthquake sources, and Earth structure.',
      favicon: '/favicon.svg',
      social: [{ icon: 'github', label: 'Original course repository', href: 'https://github.com/CUSeismoLab/Tutorial-post' }],
      customCss: ['katex/dist/katex.min.css', './src/styles/custom.css'],
      components: { Hero: './src/components/Hero.astro' },
      tableOfContents: { minHeadingLevel: 2, maxHeadingLevel: 3 },
      sidebar: [
        { label: 'Start here', items: [
          { label: 'Introduction', slug: 'intro' },
        ] },
        { label: 'Entry level', items: [
          { label: 'Unix commands', slug: 'unix' },
          { label: 'GMT: Topographic maps', slug: 'gmt6-1' },
          { label: 'GMT: Seismic data', slug: 'gmt6-2' },
          { label: 'ObsPy: Request data', slug: 'obspy-1' },
          { label: 'ObsPy: Process data', slug: 'obspy-2' },
        ] },
        { label: 'Intermediate level', items: [
          { label: 'STA/LTA earthquake detection', slug: 'sta_lta' },
          { label: 'Absolute earthquake location', slug: 'abs_loc' },
        ] },
        { label: 'Advanced level', items: [
          { label: 'Focal mechanisms with gCAP', slug: 'gcap' },
          { label: 'FK & CAP installation', slug: 'fk' },
          { label: 'Earthquake Transformer', slug: 'eqt' },
          { label: 'Double-difference relocation', slug: 'dd_loc' },
          { label: 'Spectral analysis', slug: 'source_spectra' },
          { label: 'Static stress change with PyLith', slug: 'pylith_static' },
          { label: 'Dynamic rupture simulation', slug: 'pylith_dynamic' },
          { label: 'Body wave tomography', slug: 'body_tomo' },
          { label: 'Surface wave tomography', slug: 'surface_tomo' },
          { label: 'Ambient noise cross correlation', slug: 'ambient_tomo' },
        ] },
        { label: 'Resources', items: [
          { label: 'Acknowledgement', slug: 'appendix' },
          { label: 'How to contribute', slug: 'intro/git-update' },
          { label: 'GMT: Complete original tutorial', slug: 'gmt6' },
          { label: 'Give us feedback', link: 'https://docs.google.com/forms/d/e/1FAIpQLScSQIcOtANjTonJDhK4KYmoA6H2lUHou9Mqz1oFCHSTd5wxhQ/viewform?usp=sf_link' },
        ] },
      ],
    }),
  ],
});
