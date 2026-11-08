# Udyam Sathi

Udyam Sathi is a mobile-first, voice-first onboarding prototype for synthetic Indian small-business leads. The fictional operator is **Accel Business**. The demo includes an English/Hindi advisor and interface, deterministic eligibility and pricing, quote add-ons, mock GSTIN/Udyam lookups, consent-led specimen document checks, order tracking, a partner console, and a webhook-style WhatsApp adapter. The language switch localizes customer and partner pages, the advisor’s next response, and browser speech recognition and spoken reply locale.

> All supplied registry records, businesses, people, identifiers, and KYC images are synthetic. Specimen documents are not valid identity documents.

## Run locally

Install Python 3.11, Node.js, and `make` (or run the commands below separately). Install the declared packages, then start the app:

```sh
python -m pip install -r requirements.txt
make dev
```

The UI runs at `http://localhost:5173`; the API runs at `http://localhost:8000` and its OpenAPI docs at `/docs`. `make dev` starts both and stops the API when the UI process exits. On Windows PowerShell, `scripts/dev.ps1` is the launcher used by the Makefile. If Make is unavailable, use two terminals:

```sh
uvicorn backend.main:app --reload --port 8000
cd frontend && npm install && npm run dev
```

Install the frontend packages with `npm --prefix frontend install`. The React, Vite, Tailwind, and Lucide dependencies are declared in `frontend/package.json`. The optional `GEMINI_API_KEY` is documented in `.env.example`; when present, Gemini receives function tools backed by the deterministic rule engine. The model cannot set eligibility or author prices; the UI displays only catalogue-rule quote values. Without a key or if a model call fails, the scripted advisor keeps the demo working. Browser speech recognition varies by browser and locale; typing remains available.

For the test suite, install `requirements-dev.txt` instead of `requirements.txt` before running `make test`.

## Deploy the backend to Railway

The root `Dockerfile` runs the FastAPI service and copies the synthetic CSV data it needs. In Railway, create a project from this GitHub repository and deploy from the repository root. Railway detects the Dockerfile and supplies the `PORT` variable. Generate a public domain, then verify `https://YOUR-RAILWAY-DOMAIN/api/health` returns `{"ok":true,...}`. For persistent demo orders, attach a volume mounted at `/var/data` and set `DB_PATH=/var/data/udyamsathi.db`; without a volume, the SQLite demo data resets when Railway replaces the container.

## Deploy the frontend to Vercel

Import the same GitHub repository into Vercel and set **Root Directory** to `frontend`. Use the Vite preset, build command `npm run build`, and output directory `dist`. Set the Production environment variable `VITE_API_BASE_URL` to `https://YOUR-RAILWAY-DOMAIN/api`, then redeploy. The browser frontend sends API requests to Railway; the Vercel rewrite serves React routes such as `/quote` and `/track` from `index.html`. Confirm the Railway health URL first, then open the Vercel URL and send a chatbot message.

## Demo journeys

- `/chat` — advisor chat with Hindi/English voice input and spoken replies.
- `/quote` — catalogue range, expected monthly price, setup fees, install estimate, and add-ons.
- `/kyc` — itemised optional consent, CSV registry lookups, and temporary specimen validation.
- `/track/:orderId` — order state and expected-by date, with a demo-only advance control.
- `/partner` — sorted synthetic follow-up queue and lead KPIs.
- `POST /api/whatsapp/webhook` — mock adapter accepting `{ "message": "...", "profile": {} }`.

Run `python scripts/seed_demo.py` to write three demo personas to `data/demo_personas.json`. Use any GSTIN or Udyam number present in the corresponding CSV for a successful registry lookup. Never upload real identity documents to this prototype. A silent, captioned 72-second feature walkthrough is available at [docs/udyam-sathi-walkthrough.webm](docs/udyam-sathi-walkthrough.webm).

## Rules and pricing

`backend/rules.py` is the pricing and eligibility source of truth. Prices, setup fees, contract durations, and install estimates are loaded from `data/product_catalogue.csv`. GSTIN restrictions, tier, employee and site minimums are checked by the backend; dependent add-ons must also include a required base product. Quote totals are quantity-adjusted and use the min/max range midpoint for the expected monthly amount.

## Partner model

The partner propensity model is a standard-library logistic regression trained on the supplied leads, using segment, GSTIN status, city tier, employee count, sites, lead source, current spend, and products of interest. On the supplied data it reaches **0.7123 holdout AUC** on a deterministic shuffled 80/20 split (1,000 holdout leads). Highest-magnitude learned signals include segment (`Micro retail & services`, -0.4952), GSTIN status (`N`, -0.4485), city tier 2 (-0.4393), and Website form (-0.2796). Execute `python -m backend.partner_model` to reproduce the AUC and feature ranking. The API uses its predictions to sort dropped leads. Model metrics are also returned from `/api/partner/metrics`.

The partner queue is a prototype follow-up aid, not an underwriting or eligibility decision. KYC records and uploaded files are not returned to the partner API.

## Checks

```sh
pytest -q
python scripts/audit_kyc.py
```

The tests cover city tier, employee and site minimums, GSTIN restrictions, dependency checks, monthly totals, setup fee and term aggregation, and eight advisor scenarios. The KYC audit enumerates every supplied PNG and tries local Tesseract OCR for synthetic specimen markers. The API also treats files in the supplied `K01_`…`K12_` fixture set as synthetic and never retains uploaded image bytes. Without Tesseract, image text extraction is not available and review is required.

## Layout

```text
backend/       FastAPI routes, advisor, pricing rules, partner model
frontend/      React + Vite mobile UI
data/          supplied synthetic CSVs and 47 KYC specimen PNGs
tests/         rule and scripted advisor coverage
docs/          walkthrough and component architecture
scripts/       dev launcher, demo personas, KYC fixture audit
```

See [docs/demo_script.md](docs/demo_script.md) and [docs/architecture.md](docs/architecture.md).
