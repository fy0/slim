from typing import Optional, List

from schematics import Model

from slim.utils.jsdict import JsDict


class TempStorage(JsDict):
    validated_query: Optional[Model]
    validated_post: Optional[Model]
    validated_write_values: Optional[List[Model]]
