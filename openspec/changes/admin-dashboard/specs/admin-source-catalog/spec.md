## Purpose

Lets a reviewer see every source document GovAssist relies on, including
how its text was actually extracted, so a lower-confidence extraction
gets the closer look it warrants.

## ADDED Requirements

### Requirement: Source list reflects live data
The dashboard SHALL list all live `SOURCE_DOCUMENT` rows with URL, type,
status, fetched date, content hash, extraction method, and which
services it supports.

#### Scenario: Every live source document appears
- **WHEN** the source catalog is loaded
- **THEN** every row currently in the live `SOURCE_DOCUMENT` table
  appears, with its actual fetch date, content hash, and status

### Requirement: Extraction method is shown explicitly
Each source document's extraction method SHALL be shown explicitly
(e.g. pdfplumber text layer, Tesseract OCR, Gemini Flash vision, or
Claude last-resort), so a Tesseract- or vision-derived extraction is
visibly distinguishable from a native text-layer extraction.

#### Scenario: A scanned-PDF source shows its OCR method
- **WHEN** the source catalog shows a document that required OCR
  fallback rather than a native text layer
- **THEN** the specific extraction method actually used for that
  document is shown, not a generic "extracted" label

### Requirement: Adding a source records intent without live ingestion
Adding a URL or uploading a PDF through the dashboard SHALL record the
intent as an `ADMIN_OVERLAY` row and show it as pending in the
dashboard's own view. It SHALL NOT trigger the live scraping, PDF
extraction, chunking, or embedding pipeline, and the dashboard SHALL
make this non-triggering explicit in the UI rather than silently doing
nothing.

#### Scenario: Added source is visibly pending, not silently ignored
- **WHEN** a reviewer adds a URL or uploads a PDF
- **THEN** the dashboard shows it as a pending overlay entry with a
  visible note that live ingestion was not triggered, and no
  `SOURCE_DOCUMENT` or `DOCUMENT_CHUNK` row is created in the live
  tables
