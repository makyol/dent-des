# DentDES Explorer

This static site exposes the verified DentDES outputs in a browser. It is a results explorer, not a second implementation of the Python simulator: the charts and metrics are loaded from the archived synthetic experiment outputs.

## Local use

Serve this directory from a local web server so the browser can load the CSV files. Opening `index.html` directly may block those requests in some browsers.

## GitHub Pages

Publish the contents of this directory as the Pages site, or copy them to a dedicated `gh-pages` branch. Keep the three CSV files under `data/` at the same relative path. The site has no server-side runtime and does not collect user data.

## Scope

The site uses synthetic inputs and reports the 50-block results used in the manuscript. It does not provide clinical advice and does not represent a live AI, IoT, or digital-twin deployment.
