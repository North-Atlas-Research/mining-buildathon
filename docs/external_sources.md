# External-reference-only sources

Some public sources may be inspected and used for factual extraction without
permission to redistribute the original artifact. These sources remain distinct
from the immutable Raw dataset and `metadata/raw_manifest.csv`.

For each external-reference-only source, `metadata/external_source_manifest.csv`
records the publisher, title, official artifact and index URLs, source version,
HTTP Last-Modified value, access date, byte size, SHA-256, redistribution status,
and the reason the original is not retained in Raw.

Permitted redistribution statuses are `not_authorized` and
`unclear_no_redistribution`. Original artifacts with either status must not be
committed, published, bundled with deliverables, copied to shared Raw, or
redistributed. A temporary download may be checked against the pinned byte size
and SHA-256 and must remain outside the repository and shared data directories.

Curated factual extraction tables may be stored beneath
`metadata/external_sources/` when they preserve source values and carry stable
page and row references. They must not contain source pages, screenshots, layout
reproductions, embedded files, or extended verbatim passages.
