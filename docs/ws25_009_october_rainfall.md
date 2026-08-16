# WS25-009 October rainfall

The canonical source is NASA GPM IMERG Final Run `GPM_3IMERGHH_07` V07B. Raw HDF5 fields are `Grid/precipitation`, rate in `mm/hr`, on native 0.1 degree centre-registered cells. The Jamaican October 5–7 event is `[2020-10-05T05:00Z, 2020-10-08T05:00Z)`; acquisition includes one antecedent and one decay day.

Source intervals are start-labelled; processed timestamps are end-labelled, so time `T` represents `[T-30 minutes,T)`. Half-hour depth is rate times 0.5 hours. Trailing 1h, 3h, 6h and 24h totals require respectively 2, 6, 12 and 48 valid intervals; missing data propagates. The event total requires all 144 event intervals.

The processed NetCDF retains every native cell whose bounds intersect the frozen 2 km Portmore context, without resampling, interpolation, reprojection, or downscaling. It is rainfall context only, not flood depth, flooded-road status, road closure, road failure probability, accessibility penalty, or shelter impact.
