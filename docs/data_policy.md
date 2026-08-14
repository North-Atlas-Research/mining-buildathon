# Data Policy

## Data lifecycle

```text
Raw -> Interim -> Processed -> Outputs
             \-> Scratch
Cache is re-downloadable and disposable.
```

## Raw

Exact downloaded/source artifacts.

Rules:
- immutable;
- read-only mount;
- preserve original filenames when practical;
- record hash and provenance;
- never silently replace a source artifact.

## Interim

Mechanical transforms such as:
- decompression;
- clipping;
- reprojection;
- format conversion;
- extraction.

Interim artifacts should be reproducible from Raw.

## Processed

Canonical normalized datasets consumed by downstream project code.

Examples:
- normalized shelter table;
- community GeoPackage/Parquet;
- canonical road graph;
- accumulated rainfall rasters;
- standardized observation records.

## Outputs

Human-facing or evaluation artifacts:
- maps;
- reports;
- summary tables;
- validation outputs.

## Scratch

Disposable experimentation. Nothing required for reproducibility should exist only here.

## Cache

Artifacts safe to delete and reacquire.
