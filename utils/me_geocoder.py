"""
Middle East Geocoder
A static gazetteer mapping Middle East location names (Arabic + English) to
geographic coordinates and the country they belong to.

Used by the Sabereen News explosion monitor to place reported strikes/explosions
on a map. No network calls — purely a local lookup table.

The `country` field matches the `properties.name` field in
`assets/countries.geo.json` so the map renderer can fill the right country
polygon. Where the GeoJSON has no matching polygon (e.g. the Gaza Strip), the
country is set to None and only a point + radius circle is drawn.
"""
import re
from typing import Optional

# ─── Gazetteer ───
# Each entry maps a canonical id to display names, coordinates, the GeoJSON
# country name (or None), and extra alias strings to match in raw text.
ME_LOCATIONS: dict[str, dict] = {
    # ───────────── South Lebanon ─────────────
    "khiam": {"en": "Khiam", "ar": "الخيام", "lat": 33.3306, "lon": 35.6361, "country": "Lebanon", "aliases": ["الخيّام"]},
    "bint_jbeil": {"en": "Bint Jbeil", "ar": "بنت جبيل", "lat": 33.1206, "lon": 35.4314, "country": "Lebanon", "aliases": ["بنت جبيّل"]},
    "bayada": {"en": "Bayada", "ar": "البياضة", "lat": 33.1019, "lon": 35.2078, "country": "Lebanon", "aliases": ["البيّاضة"]},
    "naqoura": {"en": "Naqoura", "ar": "الناقورة", "lat": 33.1167, "lon": 35.1389, "country": "Lebanon", "aliases": ["الناقوره"]},
    "tyre": {"en": "Tyre", "ar": "صور", "lat": 33.2705, "lon": 35.2038, "country": "Lebanon", "aliases": []},
    "nabatieh": {"en": "Nabatieh", "ar": "النبطية", "lat": 33.3789, "lon": 35.4839, "country": "Lebanon", "aliases": ["النبطيّة"]},
    "marjayoun": {"en": "Marjayoun", "ar": "مرجعيون", "lat": 33.3608, "lon": 35.5917, "country": "Lebanon", "aliases": []},
    "aitaroun": {"en": "Aitaroun", "ar": "عيترون", "lat": 33.1006, "lon": 35.4036, "country": "Lebanon", "aliases": []},
    "maroun_al_ras": {"en": "Maroun al-Ras", "ar": "مارون الراس", "lat": 33.0911, "lon": 35.4181, "country": "Lebanon", "aliases": []},
    "kfar_kila": {"en": "Kfar Kila", "ar": "كفركلا", "lat": 33.3433, "lon": 35.5731, "country": "Lebanon", "aliases": ["كفر كلا"]},
    "adaisseh": {"en": "Adaisseh", "ar": "العديسة", "lat": 33.3231, "lon": 35.5742, "country": "Lebanon", "aliases": []},
    "rmaish": {"en": "Rmaish", "ar": "رميش", "lat": 33.0917, "lon": 35.3667, "country": "Lebanon", "aliases": []},
    "yaroun": {"en": "Yaroun", "ar": "يارون", "lat": 33.0617, "lon": 35.4286, "country": "Lebanon", "aliases": []},
    "aita_al_shaab": {"en": "Aita al-Shaab", "ar": "عيتا الشعب", "lat": 33.0975, "lon": 35.3970, "country": "Lebanon", "aliases": ["عيتا الشّعب"]},
    "blida": {"en": "Blida", "ar": "بليدا", "lat": 33.2450, "lon": 35.5660, "country": "Lebanon", "aliases": []},
    "meiss_el_jabal": {"en": "Meiss el-Jabal", "ar": "ميس الجبل", "lat": 33.2089, "lon": 35.5542, "country": "Lebanon", "aliases": []},
    "houla": {"en": "Houla", "ar": "حولا", "lat": 33.2108, "lon": 35.5042, "country": "Lebanon", "aliases": []},
    "beirut": {"en": "Beirut", "ar": "بيروت", "lat": 33.8938, "lon": 35.5018, "country": "Lebanon", "aliases": []},
    "dahiyeh": {"en": "Dahiyeh (Beirut)", "ar": "الضاحية الجنوبية", "lat": 33.8500, "lon": 35.5000, "country": "Lebanon", "aliases": ["الضاحية"]},
    "baalbek": {"en": "Baalbek", "ar": "بعلبك", "lat": 34.0058, "lon": 36.2181, "country": "Lebanon", "aliases": []},

    # ───────────── Israel (incl. occupied Golan) ─────────────
    "tel_aviv": {"en": "Tel Aviv", "ar": "تل أبيب", "lat": 32.0853, "lon": 34.7818, "country": "Israel", "aliases": []},
    "haifa": {"en": "Haifa", "ar": "حيفا", "lat": 32.7940, "lon": 34.9896, "country": "Israel", "aliases": []},
    "kiryat_shmona": {"en": "Kiryat Shmona", "ar": "كريات شمونة", "lat": 33.2074, "lon": 35.5695, "country": "Israel", "aliases": ["كريات شمونه"]},
    "nahariya": {"en": "Nahariya", "ar": "نهاريا", "lat": 33.0058, "lon": 35.0950, "country": "Israel", "aliases": []},
    "metula": {"en": "Metula", "ar": "المطلة", "lat": 33.2786, "lon": 35.5786, "country": "Israel", "aliases": ["مستعمرة المطلة"]},
    "safed": {"en": "Safed", "ar": "صفد", "lat": 32.9646, "lon": 35.4960, "country": "Israel", "aliases": []},
    "tiberias": {"en": "Tiberias", "ar": "طبريا", "lat": 32.7959, "lon": 35.5310, "country": "Israel", "aliases": []},
    "acre": {"en": "Acre", "ar": "عكا", "lat": 32.9281, "lon": 35.0820, "country": "Israel", "aliases": []},
    "jerusalem": {"en": "Jerusalem", "ar": "القدس", "lat": 31.7683, "lon": 35.2137, "country": "Israel", "aliases": []},
    "karmiel": {"en": "Karmiel", "ar": "كرميئيل", "lat": 32.9192, "lon": 35.2961, "country": "Israel", "aliases": []},
    "shlomi": {"en": "Shlomi", "ar": "شلومي", "lat": 33.0764, "lon": 35.1453, "country": "Israel", "aliases": []},
    "golan": {"en": "Occupied Golan", "ar": "الجولان المحتل", "lat": 32.9500, "lon": 35.7500, "country": "Israel", "aliases": ["الجولان"]},

    # ───────────── Gaza Strip (no GeoJSON polygon → point only) ─────────────
    "gaza_city": {"en": "Gaza City", "ar": "مدينة غزة", "lat": 31.5017, "lon": 34.4668, "country": None, "aliases": []},
    "khan_younis": {"en": "Khan Younis", "ar": "خان يونس", "lat": 31.3444, "lon": 34.3030, "country": None, "aliases": []},
    "rafah": {"en": "Rafah", "ar": "رفح", "lat": 31.2968, "lon": 34.2436, "country": None, "aliases": []},
    "jabalia": {"en": "Jabalia", "ar": "جباليا", "lat": 31.5278, "lon": 34.4831, "country": None, "aliases": []},
    "beit_hanoun": {"en": "Beit Hanoun", "ar": "بيت حانون", "lat": 31.5378, "lon": 34.5364, "country": None, "aliases": []},
    "deir_al_balah": {"en": "Deir al-Balah", "ar": "دير البلح", "lat": 31.4181, "lon": 34.3508, "country": None, "aliases": []},

    # ───────────── Syria ─────────────
    "damascus": {"en": "Damascus", "ar": "دمشق", "lat": 33.5138, "lon": 36.2765, "country": "Syria", "aliases": []},
    "aleppo": {"en": "Aleppo", "ar": "حلب", "lat": 36.2021, "lon": 37.1343, "country": "Syria", "aliases": []},
    "homs": {"en": "Homs", "ar": "حمص", "lat": 34.7308, "lon": 36.7090, "country": "Syria", "aliases": []},
    "latakia": {"en": "Latakia", "ar": "اللاذقية", "lat": 35.5196, "lon": 35.7915, "country": "Syria", "aliases": []},
    "quneitra": {"en": "Quneitra", "ar": "القنيطرة", "lat": 33.1264, "lon": 35.8244, "country": "Syria", "aliases": []},
    "daraa": {"en": "Daraa", "ar": "درعا", "lat": 32.6189, "lon": 36.1021, "country": "Syria", "aliases": []},

    # ───────────── Yemen ─────────────
    "sanaa": {"en": "Sana'a", "ar": "صنعاء", "lat": 15.3694, "lon": 44.1910, "country": "Yemen", "aliases": []},
    "hodeidah": {"en": "Hodeidah", "ar": "الحديدة", "lat": 14.7978, "lon": 42.9545, "country": "Yemen", "aliases": []},
    "saada": {"en": "Saada", "ar": "صعدة", "lat": 16.9402, "lon": 43.7637, "country": "Yemen", "aliases": []},
    "taiz": {"en": "Taiz", "ar": "تعز", "lat": 13.5795, "lon": 44.0209, "country": "Yemen", "aliases": []},
    "marib": {"en": "Marib", "ar": "مأرب", "lat": 15.4622, "lon": 45.3258, "country": "Yemen", "aliases": []},

    # ───────────── Iraq ─────────────
    "baghdad": {"en": "Baghdad", "ar": "بغداد", "lat": 33.3152, "lon": 44.3661, "country": "Iraq", "aliases": []},
    "erbil": {"en": "Erbil", "ar": "أربيل", "lat": 36.1901, "lon": 44.0091, "country": "Iraq", "aliases": []},
    "mosul": {"en": "Mosul", "ar": "الموصل", "lat": 36.3450, "lon": 43.1450, "country": "Iraq", "aliases": []},
    "basra": {"en": "Basra", "ar": "البصرة", "lat": 30.5085, "lon": 47.7804, "country": "Iraq", "aliases": []},

    # ───────────── Kuwait ─────────────
    "kuwait_city": {"en": "Kuwait City", "ar": "مدينة الكويت", "lat": 29.3759, "lon": 47.9774, "country": "Kuwait", "aliases": ["الكويت"]},
    "ali_al_salem": {"en": "Ali Al Salem Air Base", "ar": "قاعدة علي السالم الجوية", "lat": 29.3467, "lon": 47.5208, "country": "Kuwait", "aliases": ["علي السالم", "علي سالم", "قاعدة عرب"]},
    "camp_arifjan": {"en": "Camp Arifjan", "ar": "معسكر عريفجان", "lat": 28.8654, "lon": 48.1417, "country": "Kuwait", "aliases": ["عريفجان"]},
    "ahmadi": {"en": "Ahmadi", "ar": "الأحمدي", "lat": 29.0769, "lon": 48.0838, "country": "Kuwait", "aliases": []},

    # ───────────── Iran ─────────────
    "tehran": {"en": "Tehran", "ar": "طهران", "lat": 35.6892, "lon": 51.3890, "country": "Iran", "aliases": []},
    "isfahan": {"en": "Isfahan", "ar": "أصفهان", "lat": 32.6546, "lon": 51.6680, "country": "Iran", "aliases": []},
    "qeshm": {"en": "Qeshm Island", "ar": "جزيرة قشم", "lat": 26.9581, "lon": 56.2719, "country": "Iran", "aliases": ["قشم"]},
    "bandar_abbas": {"en": "Bandar Abbas", "ar": "بندر عباس", "lat": 27.1865, "lon": 56.2808, "country": "Iran", "aliases": []},
    "natanz": {"en": "Natanz", "ar": "نطنز", "lat": 33.5128, "lon": 51.9161, "country": "Iran", "aliases": []},
    "bushehr": {"en": "Bushehr", "ar": "بوشهر", "lat": 28.9234, "lon": 50.8203, "country": "Iran", "aliases": []},

    # ───────────── Egypt / Sinai ─────────────
    "cairo": {"en": "Cairo", "ar": "القاهرة", "lat": 30.0444, "lon": 31.2357, "country": "Egypt", "aliases": []},
    "el_arish": {"en": "El Arish (Sinai)", "ar": "العريش", "lat": 31.1316, "lon": 33.7984, "country": "Egypt", "aliases": []},
}

# Region-level fallbacks: matched only if no specific city above is found.
# These map broad region phrases to a representative centroid + country.
ME_REGIONS: dict[str, dict] = {
    "south_lebanon": {"en": "South Lebanon", "ar": "جنوب لبنان", "lat": 33.2000, "lon": 35.4000,
                      "country": "Lebanon", "aliases": ["جنوبي لبنان", "الجنوب اللبناني"]},
    "lebanon": {"en": "Lebanon", "ar": "لبنان", "lat": 33.8547, "lon": 35.8623, "country": "Lebanon", "aliases": []},
    "gaza": {"en": "Gaza Strip", "ar": "قطاع غزة", "lat": 31.4000, "lon": 34.3500, "country": None, "aliases": ["غزة"]},
    "west_bank": {"en": "West Bank", "ar": "الضفة الغربية", "lat": 32.0000, "lon": 35.3000, "country": "West Bank", "aliases": []},
    "syria": {"en": "Syria", "ar": "سوريا", "lat": 34.8021, "lon": 38.9968, "country": "Syria", "aliases": ["سورية"]},
    "yemen": {"en": "Yemen", "ar": "اليمن", "lat": 15.5527, "lon": 48.5164, "country": "Yemen", "aliases": []},
    "iraq": {"en": "Iraq", "ar": "العراق", "lat": 33.2232, "lon": 43.6793, "country": "Iraq", "aliases": []},
    "iran": {"en": "Iran", "ar": "إيران", "lat": 32.4279, "lon": 53.6880, "country": "Iran", "aliases": ["ايران"]},
    "israel": {"en": "Israel", "ar": "إسرائيل", "lat": 31.5000, "lon": 34.9000, "country": "Israel", "aliases": ["اسرائيل", "فلسطين المحتلة"]},
}


def _candidate_strings(entry: dict) -> list[str]:
    """All strings that should match this entry (Arabic, English, aliases)."""
    out = [entry["ar"], entry["en"]]
    out.extend(entry.get("aliases", []))
    return [s for s in out if s]


# A "letter" for boundary purposes: a Unicode word char that is not a digit or
# underscore (covers Arabic and Latin letters). Used to ensure a candidate is a
# whole word, so e.g. "صور" (Tyre) does NOT match inside "صورة" (image).
_LETTER = r"[^\W\d_]"


def _compile_candidates(table: dict) -> list[tuple]:
    """Pre-compile word-boundary regexes for every candidate string, sorted by
    descending length so the longest (most specific) match is tried first."""
    compiled: list[tuple[int, "re.Pattern", dict]] = []
    for entry in table.values():
        for cand in _candidate_strings(entry):
            pattern = re.compile(
                rf"(?<!{_LETTER}){re.escape(cand.lower())}(?!{_LETTER})"
            )
            compiled.append((len(cand), pattern, entry))
    compiled.sort(key=lambda t: t[0], reverse=True)
    return compiled


# Pre-computed once at import (the gazetteer is static).
_CITY_CANDIDATES = _compile_candidates(ME_LOCATIONS)
_REGION_CANDIDATES = _compile_candidates(ME_REGIONS)


def _entry_to_result(e: dict) -> dict:
    return {"name_en": e["en"], "name_ar": e["ar"], "lat": e["lat"],
            "lon": e["lon"], "country": e["country"]}


def geocode(text: str) -> Optional[dict]:
    """
    Scan free text (Arabic and/or English) for a known Middle East location.

    Matches whole words only (so short names like "صور"/Tyre do not match inside
    longer words). Tries specific cities/towns first (longest match wins), then
    falls back to broad region phrases. Returns a dict with keys:
        name_en, name_ar, lat, lon, country
    or None if no known location is found.
    """
    if not text:
        return None
    haystack = text.lower()

    # 1) Specific cities/towns — candidates are sorted longest-first.
    for _, pattern, entry in _CITY_CANDIDATES:
        if pattern.search(haystack):
            return _entry_to_result(entry)

    # 2) Region-level fallback.
    for _, pattern, entry in _REGION_CANDIDATES:
        if pattern.search(haystack):
            return _entry_to_result(entry)

    return None
