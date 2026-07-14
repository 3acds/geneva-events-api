from dataclasses import asdict, dataclass, fields
from datetime import date, datetime


@dataclass(slots=True)
class Event:
    id: str = ""
    img: str = ""
    title: str = ""
    date: object = None
    day: int | None = None
    month: int | None = None
    year: int | None = None
    description: str = ""
    tag: str = ""
    source_url: str = ""
    start_at: object = None
    end_at: object = None
    has_start_time: bool = False
    raw_date: str = ""
    price_type: str = "unknown"
    source: str = ""
    scraped_at: object = None
    updated_at: object = None

    @classmethod
    def from_document(cls, document):
        data = document.to_dict() or {}
        data.setdefault("id", document.id)
        allowed = {field.name for field in fields(cls)}
        return cls(**{key: value for key, value in data.items() if key in allowed})

    def to_dict(self):
        result = asdict(self)
        for key in ("date", "start_at", "end_at", "scraped_at", "updated_at"):
            if isinstance(result[key], (date, datetime)):
                result[key] = result[key].isoformat()
        return result
