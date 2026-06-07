# ChromiumFish docs

Documentation site, built with [Just the Docs](https://just-the-docs.com) (a Jekyll theme)
and deployed to GitHub Pages.

## Local preview

Requires Ruby 3.x and Bundler.

```bash
cd docs
bundle install
bundle exec jekyll serve   # live preview at http://localhost:4000/chromiumfish/
```

## Structure

```
docs/
├── _config.yml          # theme, navigation, site metadata
├── Gemfile              # jekyll + just-the-docs
├── index.md             # Home
├── installation.md
├── quickstart.md
├── personas.md
├── api/                 # API Reference (python · javascript)
├── _includes/           # head_custom.html (favicon)
└── favicon.png
```

Page order is set per file via the `nav_order` front-matter key; nested pages use
`parent`. There's no central navigation file to maintain.

## Deploying

A GitHub Actions workflow (`.github/workflows/docs.yml`) builds the site and publishes it
on every push to `main` that touches `docs/`. Enable it once under
**Settings → Pages → Build and deployment → Source = GitHub Actions**. The site then lives
at <https://chromiumfish.com>.
