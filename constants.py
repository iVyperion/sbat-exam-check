from datetime import datetime, timedelta

AVAILABLE_URL = "https://api-rijbewijs.sbat.be/praktijk/api/exam/available"
SBAT_LOGIN_URL = "https://rijbewijs.sbat.be/praktijk/examen/login"
USER_AGENT = "SBAT Exam Check GUI (github.com/fre-db/sbat-exam-check)"
CENTER_IDS = [
    (7, "Brakel"),
    (10, "Sint-Niklaas"),
    (1, "St-Denijs"),
    (9, "Erembodegem"),
    (8, "Eeklo"),
]
PAYLOAD_BASE = {
    "licenseType": "B",
    "examType": "E2",
    "startDate": f"{(datetime.now() + timedelta(hours=24)).strftime('%Y-%m-%d')}T00:00",
}

# An example response from the SBAT API
response_example = [
    {
        "id": 316276,
        "typesBlob": '["B"]',
        "examTypesBlob": '["E2"]',
        "examType": "E2",
        "from": "2024-08-30T10:15:00",
        "till": "2024-08-30T11:10:00",
        "dayScheduleId": 135,
        "examCenterId": 7,
        "drivingSchool": None,
        "examinee": None,
        "isPublic": True,
    },
    {
        "id": 316289,
        "typesBlob": '["B"]',
        "examTypesBlob": '["E2"]',
        "examType": "E2",
        "from": "2024-08-30T09:20:00",
        "till": "2024-08-30T10:15:00",
        "dayScheduleId": 131,
        "examCenterId": 7,
        "drivingSchool": None,
        "examinee": None,
        "isPublic": True,
    },
    {
        "id": 316341,
        "typesBlob": '["B"]',
        "examTypesBlob": '["E2"]',
        "examType": "E2",
        "from": "2024-08-30T11:10:00",
        "till": "2024-08-30T12:05:00",
        "dayScheduleId": 131,
        "examCenterId": 7,
        "drivingSchool": None,
        "examinee": None,
        "isPublic": True,
    },
    {
        "id": 340213,
        "typesBlob": '["B"]',
        "examTypesBlob": '["E2"]',
        "examType": "E2",
        "from": "2024-08-30T16:05:00",
        "till": "2024-08-30T17:00:00",
        "dayScheduleId": 131,
        "examCenterId": 7,
        "drivingSchool": None,
        "examinee": None,
        "isPublic": True,
    },
]


DAY_NAMES_NL = ["ma", "di", "wo", "do", "vr", "za", "zo"]


def slot_key(slot: dict) -> str:
    """Unique key for a slot: its start as 'YYYY-MM-DDTHH:MM'."""
    return slot.get("from", "")[:16]


def format_slots(slots: list[dict]) -> list[str]:
    """
    Group slots per day with their times, e.g.
    ['vr 30/08/2024: 09:20-10:15, 10:15-11:10']
    """
    per_day: dict[str, list[str]] = {}
    for slot in sorted(slots, key=lambda s: s.get("from", "")):
        start = slot.get("from", "")
        if len(start) < 16:
            continue
        end = slot.get("till", "")
        time_str = start[11:16] + (f"-{end[11:16]}" if len(end) >= 16 else "")
        per_day.setdefault(start[:10], []).append(time_str)

    lines = []
    for day, times in per_day.items():
        try:
            d = datetime.strptime(day, "%Y-%m-%d")
            label = f"{DAY_NAMES_NL[d.weekday()]} {d.strftime('%d/%m/%Y')}"
        except ValueError:
            label = day
        lines.append(f"{label}: {', '.join(times)}")
    return lines
