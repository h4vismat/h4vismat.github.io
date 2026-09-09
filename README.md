# Lucca Godoy's personal blog

A small Hugo site with Markdown posts, optional tags, and static HTML output.
The homepage shows the five newest posts; `/writing/` contains the full archive,
`/tags/` groups posts by subject, and `/about/` holds the biography and contacts.
Published writing is available as RSS at `/index.xml`.

## Local setup

Use **Hugo 0.165.0**, the version pinned in `.hugo-version`. The standard edition
is sufficient. Download the matching binary or macOS package from the
[official release](https://github.com/gohugoio/hugo/releases/tag/v0.165.0),
verify it against the release checksums, and put `hugo` on your PATH.
No Node.js, Go compiler, theme download, or database is required.

```sh
hugo version
hugo server --buildDrafts
```

Open the local URL printed by Hugo, normally `http://localhost:1313/`.
Changes to Markdown and templates update the local preview.
This workspace also has an ignored local binary at `.tools/hugo`; use it in
place of `hugo` if you have not installed Hugo on your PATH.

## Write a post

```sh
hugo new content writing/my-first-post.md
```

The writing archetype creates a draft with these fields:

```yaml
---
title: "My first post"
date: 2026-09-08
description: "A short description for search results and link previews."
tags: ["life", "philosophy"]
draft: true
---

Your text goes here.
```

- **Title and date are required.** Dates without an offset use
  `America/Fortaleza`. Both date-only values and timestamp values are supported.
- **Tags are optional.** Use `tags: []` or omit the field for an untagged post.
  Keep spelling lowercase and consistent. A post can have several tags; tag
  pages and their counts are generated automatically from published writing.
- **Description is optional.** When omitted, the site uses a short excerpt.
- **Drafts stay out of production.** Preview them with `--buildDrafts`, then
  change `draft` to `false` when ready. A draft committed to a public repository
  is still readable in the repository.
- **Future dates stay out of production too.** Use `--buildFuture` to preview
  them. The site needs a new build after their date arrives; publishing is
  triggered by a push to `main` or a manual workflow run, not a scheduled job.
- **Keep URLs stable.** The filename determines `/writing/my-first-post/`.
  Set `slug: "my-first-post"` before renaming the file if you want the URL to
  stay the same.

`content/writing/example.md` is an unpublished formatting example. Replace it
with your own writing or delete it. The public site intentionally starts with
an empty archive rather than fabricated posts.

Markdown supports headings, lists, links, quotations, images, tables, and fenced
code blocks with syntax highlighting. For a post with images, use a page bundle:

```text
content/writing/a-walk/
  index.md
  photo.jpg
```

Reference the image with `![Describe the image](photo.jpg)`. Internal Markdown
links such as `[about](/about/)` resolve through Hugo's built-in render hooks,
so they also work when the site is hosted under a path prefix.

## Build and check

```sh
python3 -m unittest discover -s tests -v
hugo --minify --panicOnWarning
```

Tests require Python 3.9 or later and Hugo. They use temporary content copies,
leaving your posts unchanged, and cover publication filtering, tag membership,
RSS, post metadata, missing fields, internal links, and an empty archive.
Set `HUGO_BIN=/path/to/hugo` to select a specific executable for tests.

Hugo writes the site into `public/`. This directory is ignored by Git and
cleaned on each build, so withdrawing a post or changing it back to a draft
removes its old generated page. Keep only generated files in the output
directory. `hugo server` is the recommended way to preview drafts.

## Publish on GitHub Pages

The workflow in `.github/workflows/pages.yml` checks pull requests and builds
and deploys pushes to `main`. It installs the pinned Hugo release, verifies its
checksum, runs the tests, and uploads only generated output.

For the first migration, set **Settings → Pages → Build and deployment → Source**
to **GitHub Actions**, then merge or push the reviewed changes to `main`.
Keep the existing live site until that deployment succeeds. Implementation in
the local checkout alone does not change the live site.

To publish a post, set `draft: false`, commit the Markdown and any images, and
push to `main`. Check the **Build and publish blog** workflow in the Actions tab.

## Maintain or move the site

- Content: `content/`.
- HTML templates: `layouts/`.
- Typography and layout: `assets/css/site.css`.
- Site origin and Hugo settings: `hugo.toml`.
- New-post defaults: `archetypes/writing.md`.

To change hosts, update `baseURL` in `hugo.toml` (including its trailing slash),
run a fresh production build, and serve the `public/` directory on any static
host. Configure that host to serve `404.html` for missing pages. GitHub Actions
is only the deployment adapter; content and output do not depend on it.

When upgrading Hugo, update `.hugo-version`, this setup guide, and run the tests
and production build with the new version before publishing.

Planning notes under `docs/superpowers/` are local, ignored files. Do not commit
them or force-add that directory.
