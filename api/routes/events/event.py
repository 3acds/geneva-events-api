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

    @classmethod
    def from_document(cls, document):
        data = document.to_dict() or {}
        data.setdefault("id", document.id)
        allowed = {field.name for field in fields(cls)}
        return cls(**{key: value for key, value in data.items() if key in allowed})

    def to_dict(self):
        result = asdict(self)
        if isinstance(self.date, (date, datetime)):
            result["date"] = self.date.isoformat()
        return result
