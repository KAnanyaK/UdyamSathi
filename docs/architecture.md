# Architecture

```mermaid
flowchart LR
  Owner[Business owner · mobile browser] --> UI[React + Vite · chat / quote / KYC / tracker]
  UI -->|voice text + profile| Advisor[FastAPI advisor]
  Advisor --> Rules[Deterministic eligibility + pricing]
  Rules --> Catalogue[(Product catalogue CSV)]
  UI -->|registry lookup| Registries[FastAPI mock registry routes]
  Registries --> GST[(GSTIN CSV)]
  Registries --> Udyam[(Udyam CSV)]
  UI -->|consent + accepted quote| Orders[Order + consent routes]
  Orders --> DB[(SQLite · orders / append-only consent / extracted fields)]
  UI -->|temporary document bytes| KYC[KYC validation route]
  KYC -->|text + validation only| DB
  KYC -. deletes original bytes .-> KYC
  UI -->|order status| Tracker[Order state machine]
  Tracker --> DB
  UI -->|partner queue / KPIs| Partner[Partner console API]
  Partner --> Leads[(Synthetic SMB leads CSV)]
  Chat[Mock WhatsApp webhook] --> Advisor
  Gemini[Optional Gemini integration] -. key absent: scripted advisor .-> Advisor
```

The catalogue is the only source for monthly prices, setup fees, contract terms, and install estimates. Eligibility, recommendation validation, and price aggregation are deterministic backend functions. The current advisor uses the deterministic fallback; the UI's speech input/output uses browser Web Speech APIs when available. KYC images supplied for this demo are synthetic specimens. The upload route returns a specimen warning and retains no image bytes; live OCR requires an installed Tesseract executable and is not used to approve identity.

The consent ledger appends the four purpose choices at order creation. Orders are stored in local SQLite. GSTIN and Udyam lookups are read-only CSV-backed mock APIs. The partner console reads only lead pipeline fields and never exposes the KYC table.
