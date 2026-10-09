# deepbuild-tech.github.io

Source of https://deepbuild.tech, the DeepBuild website.

Plain HTML, CSS and a little self-hosted JavaScript for animation: no build step, no third-party requests. GitHub Pages publishes the `main` branch from the repository root.

## Editing

The HTML files are the source. Every page repeats the same header and footer, so a change to either, or to the contact address, has to be made on every page. `tools/check_site.py` fails if the pages disagree.

Brand assets live in `assets/`: `deepbuild-tech-logo.svg` is the master logo, `favicon.svg` is the icon, and `og-image.png` (1200 x 630) is the link preview rendered from the logo. Re-render the preview whenever the logo changes.

## Checks before publishing

```sh
python tools/check_site.py .
python -m http.server 8080 --bind 127.0.0.1
python tools/check_site.py . --base http://127.0.0.1:8080
```

After launch, run `python tools/check_site.py . --base https://deepbuild.tech --validate` to fetch the live pages and validate them with the W3C checker.

Icons on the home page are from [Tabler Icons](https://tabler.io/icons) 3.49.0 (MIT License, Copyright (c) 2020-2024 Paweł Kuna). The workflow illustration (`assets/automation-flow.svg`) is original.

The Privacy and Terms pages are plain-language drafts and have not been reviewed by a lawyer.

Contact: hello@deepbuild.tech
