"""Prepare georeferenced display overlays from local rasters."""
import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.transform import array_bounds


def overlay(path, elevation=False):
    with rasterio.open(path) as src:
        transform, width, height = calculate_default_transform(src.crs, 'EPSG:4326', src.width, src.height, *src.bounds)
        data = np.zeros((src.count, height, width), dtype=np.float32)
        valid = np.zeros((height,width),dtype=np.uint8)
        for band in range(src.count):
            reproject(src.read(band+1),data[band],src_transform=src.transform,src_crs=src.crs,
                      dst_transform=transform,dst_crs='EPSG:4326',src_nodata=src.nodata,
                      dst_nodata=0,resampling=Resampling.nearest)
        reproject(src.dataset_mask(), valid, src_transform=src.transform,src_crs=src.crs,
                  dst_transform=transform,dst_crs='EPSG:4326',resampling=Resampling.nearest)
        if elevation:
            values = data[0][valid>0]
            low, high = float(values.min()), float(values.max())
            t = np.clip((data[0]-low)/max(high-low,1),0,1)
            rgb = np.stack([50+200*t, 170-80*t, 210-160*t],axis=-1).astype(np.uint8)
            note = f'{low:.1f}–{high:.1f} m · blue = lower, orange = higher · approximately 30 m surface model'
        else:
            rgb = np.moveaxis(data[:3],0,-1).astype(np.uint8)
            note = 'Sentinel-2 · 13 December 2025 · 10 m pixels'
        image = np.dstack([rgb,valid])
        west,south,east,north = array_bounds(height,width,transform)
        return image, [[south,west],[north,east]], note
