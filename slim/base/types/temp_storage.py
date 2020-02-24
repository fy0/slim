from typing import Optional

from schematics import Model

from slim.utils.jsdict import JsDict


class TempStorage(JsDict):
    validated_query: Optional[Model]
    validated_post: Optional[Model]
