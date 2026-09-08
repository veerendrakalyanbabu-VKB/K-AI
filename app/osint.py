"""GDACS public GeoRSS normalization; no inferred positions or local risk."""
import math
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone


def normalize_gdacs(xml):
    if not isinstance(xml, str) or len(xml) > 4000000 or "<!DOCTYPE" in xml.upper() or "<!ENTITY" in xml.upper():
        raise ValueError("Unsupported feed")
    root = ET.fromstring(xml)
    if root.tag != "rss":
        raise ValueError("Expected RSS")
    items, seen = [], set()
    for row in root.findall("./channel/item")[:300]:
        values = {child.tag.split("}")[-1]: (child.text or "").strip() for child in row}
        try:
            point = values.get("point", "").split()
            lat, lon = map(float, point) if len(point) == 2 else (float(values["lat"]), float(values["long"]))
            if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
                continue
        except (ValueError, KeyError, TypeError):
            continue
        identity = values.get("guid") or values.get("link")
        if not identity or identity in seen:
            continue
        seen.add(identity)
        timestamp = values.get("pubDate")
        try:
            timestamp = parsedate_to_datetime(timestamp).astimezone(timezone.utc).isoformat()
        except (ValueError, TypeError, OverflowError):
            try:
                dt = datetime.fromisoformat((timestamp or "").replace("Z", "+00:00"))
                timestamp = dt.isoformat() if dt.tzinfo else None
            except ValueError:
                timestamp = None
        items.append({"id": identity, "title": values.get("title") or "GDACS disaster report",
            "lat": lat, "lng": lon, "time": timestamp, "source": "GDACS · EC/JRC",
            "url": values.get("link"), "layer": "osint", "metrics": {
                "alert_level": values.get("alertlevel") or None,
                "event_type": values.get("eventtype") or None,
                "country": values.get("country") or None}})
    return items
