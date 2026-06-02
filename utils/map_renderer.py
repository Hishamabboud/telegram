"""
Explosion Map Renderer (Tzofar-style)
Renders a dark-theme map of the Middle East with the affected country filled
red and a red point marker at the exact reported location.

Uses only matplotlib + stdlib json (country polygons loaded from a committed
GeoJSON), so there are no heavy geospatial dependencies and no runtime network
calls. Designed for headless/server use (Agg backend).
"""
import json
import logging
import os
from typing import Iterator, Optional

import matplotlib
matplotlib.use("Agg")  # headless — required on the server / in Docker
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon, Circle
from matplotlib.collections import PatchCollection

logger = logging.getLogger(__name__)

# Arabic shaping for matplotlib (which has no native RTL/joining support).
# Falls back to raw text if the optional libraries are unavailable.
try:
    import arabic_reshaper
    from bidi.algorithm import get_display

    def _ar(text: str) -> str:
        """Shape + reorder Arabic so it renders correctly in matplotlib."""
        if not text:
            return text
        try:
            return get_display(arabic_reshaper.reshape(text))
        except Exception:  # pragma: no cover - defensive
            return text
except ImportError:  # pragma: no cover - optional dependency
    def _ar(text: str) -> str:
        return text

# Path to the committed country-borders GeoJSON (properties.name holds country).
GEOJSON_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets", "countries.geo.json",
)

# Middle East bounding box: lon_min, lon_max, lat_min, lat_max
ME_BBOX = (24, 64, 11, 43)

# ─── Theme ───
BG = "#0a0e14"
LAND = "#1b2430"
LAND_EDGE = "#3a4656"
CONFIRMED_FILL = (1.0, 0.17, 0.17, 0.45)   # bright red, semi-transparent
CONFIRMED_EDGE = "#ff5555"
UNCONFIRMED_FILL = (1.0, 0.55, 0.0, 0.32)  # orange, semi-transparent
UNCONFIRMED_EDGE = "#ffae42"

# Lazy-loaded GeoJSON cache (parsed once per process).
_GEO_CACHE: Optional[dict] = None


def _load_geo() -> Optional[dict]:
    global _GEO_CACHE
    if _GEO_CACHE is None:
        try:
            with open(GEOJSON_PATH, encoding="utf-8") as f:
                _GEO_CACHE = json.load(f)
        except Exception as e:  # pragma: no cover - defensive
            logger.error(f"Could not load GeoJSON at {GEOJSON_PATH}: {e}")
            return None
    return _GEO_CACHE


def _rings(geom: dict) -> Iterator[list]:
    """Yield each polygon's exterior ring for Polygon / MultiPolygon geometries."""
    t = geom.get("type")
    if t == "Polygon":
        yield geom["coordinates"][0]
    elif t == "MultiPolygon":
        for poly in geom["coordinates"]:
            yield poly[0]


def render_alert_map(
    *,
    country: Optional[str],
    lat: float,
    lon: float,
    confirmed: bool,
    label_en: str,
    label_ar: str,
    type_en: str = "",
    out_path: str = "/tmp/explosion_map.png",
) -> str:
    """
    Render the explosion map and save it to `out_path`. Returns `out_path`.

    - All Middle East countries are drawn dark with subtle borders.
    - If `country` matches a GeoJSON feature, that country is filled red
      (bright red if confirmed, orange if unconfirmed).
    - A translucent red circle + a solid red point mark the exact location.
    """
    data = _load_geo()

    fig, ax = plt.subplots(figsize=(9, 8.4), facecolor=BG)
    ax.set_facecolor(BG)

    fill_color = CONFIRMED_FILL if confirmed else UNCONFIRMED_FILL
    edge_color = CONFIRMED_EDGE if confirmed else UNCONFIRMED_EDGE

    if data:
        outlines, target = [], []
        for feat in data.get("features", []):
            is_target = country is not None and feat["properties"].get("name") == country
            for ring in _rings(feat.get("geometry", {})):
                patch = MplPolygon(ring, closed=True)
                (target if is_target else outlines).append(patch)

        if outlines:
            ax.add_collection(PatchCollection(
                outlines, facecolor=LAND, edgecolor=LAND_EDGE, linewidths=0.6))
        if target:
            ax.add_collection(PatchCollection(
                target, facecolor=fill_color, edgecolor=edge_color, linewidths=1.6))

    # Translucent "impact radius" glow around the location.
    ax.add_patch(Circle((lon, lat), radius=0.9, facecolor=fill_color,
                        edgecolor=edge_color, linewidth=1.2, zorder=4))
    # Exact location marker.
    ax.plot(lon, lat, marker="o", markersize=13, color="#ff2b2b",
            markeredgecolor="white", markeredgewidth=1.6, zorder=6)

    ax.set_xlim(ME_BBOX[0], ME_BBOX[1])
    ax.set_ylim(ME_BBOX[2], ME_BBOX[3])
    ax.set_aspect("equal")
    ax.axis("off")

    # ─── Title / status banner ───
    status_en = "CONFIRMED" if confirmed else "UNCONFIRMED"
    status_ar = "مؤكد" if confirmed else "غير مؤكد"
    banner = edge_color

    title = f"{label_en}"
    if type_en:
        title += f"  —  {type_en}"
    fig.text(0.5, 0.965, f"EXPLOSION / {_ar('انفجار')}", ha="center", va="top",
             fontsize=20, fontweight="bold", color="#ffffff")
    fig.text(0.5, 0.925, title, ha="center", va="top",
             fontsize=15, color="#e6edf3")
    fig.text(0.5, 0.895, _ar(label_ar), ha="center", va="top",
             fontsize=14, color="#c9d1d9")
    fig.text(0.5, 0.045, f"● {status_en} / {_ar(status_ar)}", ha="center", va="bottom",
             fontsize=14, fontweight="bold", color=banner)
    fig.text(0.5, 0.015, f"Sabereen News monitor  •  {_ar('مرصد سبيرين')}", ha="center", va="bottom",
             fontsize=10, color="#8b949e")

    fig.subplots_adjust(left=0.02, right=0.98, top=0.87, bottom=0.08)
    fig.savefig(out_path, dpi=130, facecolor=BG)
    plt.close(fig)
    return out_path
