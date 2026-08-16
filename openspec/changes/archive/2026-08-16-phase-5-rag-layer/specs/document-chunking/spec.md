## ADDED Requirements

### Requirement: HTML text extraction excludes navigation and footer boilerplate
Extracting text from an `html` `SourceDocument` SHALL exclude the page's
navigation menu and footer/quick-links boilerplate before the text is
split into chunks, so that boilerplate identical across every page does
not consume chunk budget or dilute a chunk's embedding.

#### Scenario: A chunk never consists mainly of navigation links
- **WHEN** an HTML page's text is extracted and chunked
- **THEN** no resulting chunk consists mainly of navigation menu items or
  footer quick-links/related-links/contact text

#### Scenario: Content-bearing text is preserved
- **WHEN** boilerplate is excluded from an HTML page's extracted text
- **THEN** every citizen-relevant sentence that was present in the page's
  main content is still present in the extracted text
