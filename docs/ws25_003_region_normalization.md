# WS25-003 region normalization

The production operational inclusion polygon is the canonical Portmore feature
in `Processed/region/portmore_boundary.gpkg`, layer
`portmore_jamaica_2020`.

The artifact at
`Interim/region/portmore_boundary_edge_review_750m.gpkg` is a two-sided 750 m
band around the canonical boundary line. It is a review-only geometry for
identifying observations near either side of the boundary. It is not the
operational inclusion polygon and must not be used to determine ordinary region
membership.

Named-area validation uses both of the following, and reports them separately:

- a representative-point inclusion Boolean;
- community-polygon diagnostics consisting of boundary intersection and the
  percentage of the community polygon intersecting the canonical boundary.

Polygon intersection percentages describe community polygons only; they do not
describe coverage of representative points.

The canonical GeoPackage and reproducible Interim and Outputs artifacts are
written beneath the mounted project data root. They are intentionally outside
Git. Git tracks the configuration, normalization code, tests, and this decision
documentation needed to reproduce and interpret those artifacts.
