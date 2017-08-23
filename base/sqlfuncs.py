import json
import logging

from .permission import A
from ..retcode import RETCODE
from ..utils import ResourceException, _valid_sql_operator

logger = logging.getLogger(__name__)


class BaseSQLFunctions:
    def __init__(self, view):
        self.err = None
        self.view = view
        self.request = view.request

    def query_order(self, text):
        """
        :param text: order=id.desc, xxx.asc
        :return: 
        """
        orders = []
        for i in text.split(','):
            items = i.split('.', 2)

            if len(items) == 1: continue
            elif len(items) == 2: column, order = items
            else: raise ResourceException("Invalid order format")

            order = order.lower()
            if column not in self.view.fields:
                raise ResourceException('Column not found: %s' % column)
            if order not in ('asc', 'desc'):
                raise ResourceException('Invalid column order: %s' % order)

            orders.append([column, order])
        return orders

    def query_convert(self, params):
        args = []
        orders = []
        ret = {
            'args': args,
            'orders': orders,
        }
        view = self.view

        for key, value in params.items():
            # xxx.{op}
            info = key.split('.', 1)

            field_name = info[0]
            if field_name == 'order':
                orders = self.query_order(value)
                continue
            elif field_name == 'with_role':
                if not value.isdigit():
                    if len(info) < 1:
                        return view.finish(RETCODE.INVALID_PARAMS, 'Invalid role id: %s' % value)
                ret['with_role'] = int(value)
                continue
            op = '='

            if field_name not in view.fields:
                return view.finish(RETCODE.INVALID_PARAMS, 'Column not found: %s' % field_name)

            if len(info) > 1:
                op = info[1]
                if op not in _valid_sql_operator:
                    return view.finish(RETCODE.INVALID_PARAMS, 'Invalid operator: %s' % op)
                op = _valid_sql_operator[op]

            # is 和 is not 可以确保完成了初步值转换
            if op in ('is', 'isnot'):
                if value.lower() != 'null':
                    return view.finish(RETCODE.INVALID_PARAMS, 'Invalid value: %s (must be null)' % value)
                if op == 'isnot':
                    op = 'is not'
                value = None

            if op == 'in':
                try:
                    value = json.loads(value)
                except json.decoder.JSONDecodeError:
                    return view.finish(RETCODE.INVALID_PARAMS, 'Invalid value: %s (must be json)' % value)

            args.append([field_name, op, value])

        logger.debug('params: %s' % ret)

        # TODO: 权限检查在列存在检查之后有暴露列的风险
        role = view.permission.request_role(view.current_user, None).can(A.QUERY)

        return ret

    async def select_one(self, select_info):
        raise NotImplementedError()
        # code, item

    async def select_count(self, select_info):
        raise NotImplementedError()
        # code, count: int

    async def select_list(self, select_info, size, offset, *, page=None):
        raise NotImplementedError()
        # code, items: iterable

    async def update(self, select_info, data):
        raise NotImplementedError()
        # code, item

    async def insert(self, data):
        raise NotImplementedError()
        # code, item

    def done(self, code, data=None):
        return code, data
