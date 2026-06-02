"""
Attack Classifier & Bilingual Caption Formatter
Extracts the attack type and confirmation status from a Sabereen News post
(Arabic, sometimes English) and builds a bilingual (English + Arabic) HTML
caption for the explosion-map photo posted to the channel.
"""
from datetime import datetime

from utils.formatter import _escape_html, get_israel_time

# ─── Attack type keywords (Arabic + English) → (English label, Arabic label) ───
# Ordered by priority: the first category with a keyword hit wins.
ATTACK_TYPES: list[tuple[list[str], str, str]] = [
    (["غارة جوية", "غارة", "قصف جوي", "airstrike", "air strike", "air raid"],
     "Airstrike", "غارة جوية"),
    (["صلية صاروخية", "صلية صاروخيّة", "صاروخ", "صواريخ", "rocket", "missile", "بصاروخ"],
     "Rocket / Missile", "صاروخ"),
    (["مسيرة", "مسيّرة", "مسيرات", "مسيّرات", "طائرة مسيرة", "درون", "drone", "uav", "انقضاضية", "انقضاضيّة"],
     "Drone strike", "مسيّرة"),
    (["قصف مدفعي", "مدفعية", "مدفعيّة", "shelling", "artillery"],
     "Artillery shelling", "قصف مدفعي"),
    (["إطلاق نار", "اشتباك", "اشتباكات", "gunfire", "clashes"],
     "Gunfire / Clashes", "إطلاق نار"),
    (["اغتيال", "assassination"],
     "Assassination", "اغتيال"),
    (["انفجار", "دوي انفجار", "تفجير", "explosion", "blast"],
     "Explosion", "انفجار"),
]

# ─── Confirmation markers ───
# If any UNCONFIRMED marker appears, treat as unconfirmed regardless.
UNCONFIRMED_MARKERS = [
    "أنباء عن", "أنباء", "نقلاً عن", "نقلا عن", "يُزعم", "يزعم", "مزاعم",
    "وردت معلومات", "سُمع دوي", "سمع دوي", "ادعى", "ادعت", "زعم",
    "غير مؤكد", "unconfirmed", "reports of", "alleged", "claims",
]
CONFIRMED_MARKERS = [
    "استهداف", "استهدف", "استهدفت", "قصف", "قصفت", "إصابة", "أصاب", "أصابت",
    "تدمير", "دمر", "دمرت", "تم استهداف", "أكد", "أكدت", "مؤكد",
    "confirmed", "targeted", "struck", "destroyed",
]


def classify_attack(text: str) -> tuple[str, str]:
    """Return (english_label, arabic_label) for the attack type found in text."""
    if not text:
        return ("Explosion", "انفجار")
    low = text.lower()
    for keywords, en, ar in ATTACK_TYPES:
        for kw in keywords:
            if kw.lower() in low:
                return (en, ar)
    return ("Explosion", "انفجار")


def is_confirmed(text: str) -> bool:
    """
    Decide whether a report is confirmed.

    An explicit unconfirmed marker always wins (returns False). Otherwise, a
    confirmed marker returns True. With neither, default to False (unconfirmed)
    — a bare "an explosion was heard" is treated as unconfirmed.
    """
    if not text:
        return False
    low = text.lower()
    for m in UNCONFIRMED_MARKERS:
        if m.lower() in low:
            return False
    for m in CONFIRMED_MARKERS:
        if m.lower() in low:
            return True
    return False


def format_attack_caption(
    *,
    location_en: str,
    location_ar: str,
    country: str | None,
    type_en: str,
    type_ar: str,
    confirmed: bool,
    source_link: str,
    timestamp: datetime | None = None,
    excerpt: str = "",
) -> str:
    """
    Build a bilingual (English then Arabic) HTML caption for the map photo.
    """
    now_str = get_israel_time(timestamp)
    status_dot = "🔴" if confirmed else "🟠"
    status_en = "CONFIRMED" if confirmed else "UNCONFIRMED"
    status_ar = "مؤكد" if confirmed else "غير مؤكد"

    region_en = f", {_escape_html(country)}" if country else ""

    lines = []
    # ═══ HEADER ═══
    lines.append(f"💥💥 <b>EXPLOSION / انفجار</b> 💥💥")
    lines.append("")
    lines.append(f"🕐 <b>{now_str}</b>")
    lines.append("")

    # ═══ ENGLISH BLOCK ═══
    lines.append(f"🗺️ <b>Location:</b> {_escape_html(location_en)}{region_en}")
    lines.append(f"🎯 <b>Type:</b> {_escape_html(type_en)}")
    lines.append(f"{status_dot} <b>Status:</b> {status_en}")
    lines.append("")

    # ═══ ARABIC BLOCK ═══
    lines.append(f"🗺️ <b>الموقع:</b> {_escape_html(location_ar)}")
    lines.append(f"🎯 <b>نوع الهجوم:</b> {_escape_html(type_ar)}")
    lines.append(f"{status_dot} <b>الحالة:</b> {status_ar}")
    lines.append("")

    if excerpt:
        lines.append(f"<i>{_escape_html(excerpt[:280])}</i>")
        lines.append("")

    # ═══ FOOTER ═══
    lines.append("─" * 24)
    if source_link:
        lines.append(f'📎 <a href="{source_link}">Source / المصدر: Sabereen News</a>')
    else:
        lines.append("<i>Source / المصدر: Sabereen News</i>")

    return "\n".join(lines)
