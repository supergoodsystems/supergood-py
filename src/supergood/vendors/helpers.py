import dataclasses
import json
from typing import List


class DataclassesJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)


@dataclasses.dataclass
class ServerSentEvent:
    """
    Storage class for streamed server side events
    """

    event: str | None
    data: List[str]
    id: str | None
    retry: int | None
