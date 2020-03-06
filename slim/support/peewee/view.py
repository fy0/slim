import logging
import peewee
from typing import Type, Tuple, List, Iterable, Union

from slim.support.peewee.sqlfuncs import PeeweeSQLFunctions
from slim.support.peewee.validate import get_pv_model_info

from ...base.sqlquery import SQLForeignKey
from ...base.permission import DataRecord, Permissions
from ...utils import get_class_full_name
from ...base.view import AbstractSQLView, SQLViewOptions

logger = logging.getLogger(__name__)


class PeeweeSQLViewOptions(SQLViewOptions):
    def __init__(self, *, list_page_size=20, list_accept_size_from_client=False, model: peewee.Model = None):
        self.model = model
        super().__init__(list_page_size=list_page_size, list_accept_size_from_client=list_accept_size_from_client)

    def assign(self, obj: Type['PeeweeView']):
        if self.model:
            obj.model = self.model
        super().assign(obj)


class PeeweeView(AbstractSQLView):
    is_base_class = True
    _sql_cls = PeeweeSQLFunctions
    options_cls = PeeweeSQLViewOptions
    model = None
    _peewee_fields = {}

    @classmethod
    def cls_init(cls, check_options=True):
        # py3.6: __init_subclass__
        if check_options:
            cls._check_view_options()

        if not cls._is_skip_check():
            if not (cls.__name__ == 'PeeweeView' and AbstractSQLView in cls.__bases__):
                assert cls.model, "%s.model must be specified." % get_class_full_name(cls)

        AbstractSQLView.cls_init.__func__(cls, False)
        # super().cls_init(False)

    @staticmethod
    async def _fetch_fields(cls_or_self):
        model = cls_or_self.model

        if model:
            info = get_pv_model_info(model)
            cls_or_self.table_name = info['table_name']
            cls_or_self.primary_key = info['primary_key']
            cls_or_self.foreign_keys = info['foreign_keys']
            cls_or_self.data_model = info['data_model']
            cls_or_self._peewee_fields = info['_peewee_fields']
