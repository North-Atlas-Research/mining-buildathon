# WS25-004 ODPEM shelter source extraction

## Source and retention decision

The external source is ODPEM's `NATIONAL SHELTER LISTING 2019`, available from
the official Portmore shelter PDF URL recorded in
`metadata/external_source_manifest.csv`. The source states `Last updated 2019`.

The PDF is external-reference-only. Its redistribution status is
`unclear_no_redistribution`, so the original is not retained in Raw, committed,
published, bundled, or redistributed. The factual extraction is attributed by
stable source identifier, printed page, row ordinal, official URLs, access date,
and pinned source checksum.

## Extraction method

The source table was checked visually against printed pages 2, 3, and 4. Values
in `metadata/external_sources/odpem_portmore_shelters_2019.csv` preserve printed
spelling, capitalization, punctuation, blanks, `N/A`, and row order. Visual line
wrapping inside cells was collapsed to spaces; this does not join or split
records. Capacity remains text. No facility type, coordinate, operating status,
or normalized capacity has been inferred.

## Section and count verification

The `PORTMORE CITY MUNICIPALITY` section contains 18 printed shelter rows:

- nine rows on printed page 2;
- nine rows on printed page 3.

Nine Portmore shelter names carry a printed `(Priority)` marker. Nine Priority
Shelter cells are populated, including the visually unusual placement of
`Kensington` on the `Independence City Primary` row while the subsequent
`Kensington (Priority)` row has a blank Priority Shelter cell. The extraction
preserves that arrangement rather than correcting it.

The source's printed total says `17` shelters and `9` priority shelters. The
priority total agrees with the rows, but the shelter total does not. The
17-versus-18 discrepancy is an internal source inconsistency: it is not caused
by PDF text extraction, a multi-line cell, or accidental inclusion of the next
section.

Printed page 4 is headed `Emergency Shelter outside Portmore` and contains two
separate records. Those records are retained in the extraction for completeness
but are classified under their own section and are not included in the 18-row
Portmore count.

## Scope boundary

This stage performs no geocoding, identity resolution, deduplication, capacity
normalization, facility-type inference, operational-status assignment, or
canonical GeoPackage generation.
