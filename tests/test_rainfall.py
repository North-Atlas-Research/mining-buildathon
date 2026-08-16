from datetime import UTC, datetime, timedelta
import numpy as np
import xarray as xr
from mining_sprint.rainfall import event_total, normalized_time, rate_to_depth, trailing_complete

def depth(count):
    start=datetime(2020,10,4,5,tzinfo=UTC)
    time=[normalized_time(start+timedelta(minutes=30*(i+1))) for i in range(count)]
    return xr.DataArray(np.ones((count,1,1)),dims=("time","lat","lon"),coords={"time":time,"lat":[0],"lon":[0]})

def test_rate_conversion_and_end_label():
    assert rate_to_depth(np.array([2.0])).item() == 1.0
    assert str(normalized_time(datetime(2020,10,5,5,30,tzinfo=UTC))) == "2020-10-05T05:30:00.000000"

def test_complete_windows_and_missing_propagation():
    value=depth(48); value.values[5,0,0]=np.nan
    assert np.isnan(trailing_complete(value,2).isel(time=0,lat=0,lon=0))
    assert trailing_complete(value,2).isel(time=2,lat=0,lon=0).item() == 2
    assert np.isnan(trailing_complete(value,6).isel(time=5,lat=0,lon=0))
    assert np.isnan(trailing_complete(value,24).isel(time=23,lat=0,lon=0))

def test_event_total_uses_exact_144_end_labelled_intervals():
    start=datetime(2020,10,5,5,tzinfo=UTC); end=datetime(2020,10,8,5,tzinfo=UTC)
    series=depth(240)
    assert event_total(series,start,end).item() == 144
