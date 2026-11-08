# HeatOpt — Deployment package (Version 12)

## Website

- `index.html` is the complete HeatOpt homeowner-facing web app. It embeds the current calculation engine, data and styling; no build tools or backend are required for the static prototype.
- To preview locally: open `index.html` in a browser, or run `python -m http.server 8000` in this directory and visit http://localhost:8000.
- To deploy: upload `index.html` to the public root of a static site host, such as Netlify, Vercel, GitHub Pages, or a conventional web server.

## Model reference source

- `model_source/heatopt/` contains the user's original Python research-model source, config, tests, and underlying data files where present. It is provided for backend integration and validation, but **is not connected to the static site**.
- Python dependencies are listed in `model_source/heatopt/requirements.txt`. Run from its parent directory or according to the project's own README.

## Important modeling notes

- The interactive page uses a browser-side, hourly/archetype-calibrated screening model with embedded inputs, not the full Python 5R1C solver.
- Its manufacturer performance curves can include interpolation and extrapolation and should be verified before sizing equipment.
- Results are preliminary and are not a substitute for an installer load calculation, approved tariffs, actual equipment quotes, or validated COMSOL analysis.
- Historical weather, emissions and energy prices should be refreshed and checked before deployment for public decision-making.
