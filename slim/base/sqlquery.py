import json
import logging
import traceback
from enum import Enum
from typing import Union, Iterable, List, TYPE_CHECKING, Dict, Set, Mapping
from typing_extensions import Literal
from multidict import MultiDict
from schematics.exceptions import DataError, ConversionError
from schematics.types import BaseType, ListType

from slim.base.const import ERR_TEXT_ROGUE_FIELD, ERR_TEXT_COLUMN_IS_NOT_FOREIGN_KEY
from slim.base.types.func_meta import get_meta
from slim.utils.schematics_ext import schematics_model_merge
from ..utils import BlobParser, JSONParser, dict_filter, dict_filter_inplace, BoolParser
from ..exception import SyntaxException, ResourceException, InvalidParams, \
    PermissionDenied, ColumnNotFound, ColumnIsNotForeignKey, SQLOperatorInvalid, InvalidRole, SlimException, \
    InvalidPostData, TableNotFound

if TYPE_CHECKING:
    from .view import BaseView, AbstractSQLView
    from .permission import Ability
    from .user import BaseUser


logger = logging.getLogger(__name__)


class NamedObject:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return '<Named Object: %s>' % self.name


PRIMARY_KEY = NamedObject('Primary Key')  # for add condition
ALL_COLUMNS = NamedObject('All Columns')


class DataRecord:
    def __init__(self, table_name, val):
        self.table = table_name
        self.val = val
        self.selected = ALL_COLUMNS
        self.available_columns = ALL_COLUMNS
        self._cache = None

    def _to_dict(self) -> Dict:
        raise NotImplementedError()

    def set_info(self, info: "SQLQueryInfo", ability: "Ability", user: "BaseUser"):
        from .permission import A
        if info:
            self.selected = info.select
        # 注意，这里实际上读了 self.keys()，所以cache已经生成了，因此直接调用reserve
        self.available_columns = ability.can_with_record(user, A.READ, self, available=info.select if info else None)
        self.reserve(self.available_columns)
        return self.available_columns

    @property
    def cache(self) -> Dict:
        if self._cache is None:
            self._cache = self._to_dict()
        return self._cache

    def get(self, key, default=None):
        return self.cache.get(key, default)

    def to_dict(self):
        return self.cache.copy()

    def keys(self):
        return self.cache.keys()

    def pop(self, key):
        return self.cache.pop(key)

    def reserve(self, keys):
        cache_keys = set(self.keys())
        for k in cache_keys - set(keys):
            del self.cache[k]

    def __getitem__(self, item):
        return self.get(item)

    def __setitem__(self, key, value):
        self.cache[key] = value

    def __delitem__(self, key):
        self.pop(key)

    def __repr__(self):
        return self.to_dict().__repr__()


class SQLForeignKey:
    def __init__(self, rel_table: str, rel_field: str, is_soft_key=False):
        self.rel_table = rel_table  # 关联的表
        self.rel_field = rel_field  # 关联的列
        # self.rel_type = rel_type  # 关联列类型
        # rel_type: SQL_TYPE,
        self.is_soft_key = is_soft_key


class SQLQueryOrder:
    def __init__(self, column, order):
        assert order in ('asc', 'desc')
        self.column = column
        self.order = order

    def __eq__(self, other):
        if isinstance(other, SQLQueryOrder):
            return self.column == other.column and self.order == other.order
        return False

    def __repr__(self):
        return '<SQLQueryOrder %r.%s>' % (self.column, self.order)


class SQL_OP(Enum):
    EQ = ('eq', '==', '=')
    NE = ('ne', '!=', '<>')
    LT = ('lt', '<')
    LE = ('le', '<=')
    GE = ('ge', '>=')
    GT = ('gt', '>')
    IN = ('in',)
    NOT_IN = ('notin', 'not in')
    IS = ('is',)
    IS_NOT = ('isnot', 'is not')
    AND = ('and',)
    OR = ('or',)
    PREFIX = ('prefix',)  # string like only
    CONTAINS = ('contains',)  # ArrayField only
    CONTAINS_ANY = ('contains_any',)  # ArrayField only
    LIKE = ('like',)
    ILIKE = ('ilike',)

    _COMMON = EQ + NE + LT + LE + GE + GT + IN + IS + IS_NOT + PREFIX + CONTAINS + CONTAINS_ANY
    _ALL = _COMMON + LIKE + ILIKE


SQL_OP.COMMON = SQL_OP._COMMON.value
SQL_OP.ALL = SQL_OP._ALL.value

SQL_OP.txt2op = {}
for i in SQL_OP:
    if i == SQL_OP._COMMON: continue
    if i == SQL_OP._ALL: continue
    for opval in i.value:
        SQL_OP.txt2op[opval] = i


class QueryConditions(list):
    """
    查询条件，这是 SQLQueryInfo 的一部分。与 list 实际没有太大不同，独立为类型的目的是使其能与list区分开来
    i[0]: str
    i[1]: SQL_OP
    i[2]: Any
    """
    def __contains__(self, item):
        for i in self:
            if i[0] == item:
                return True

    def find(self, column):
        ret = []
        for i in self:
            if i[0] == column:
                ret.append(i)
        return ret

    def map(self, key, func):
        for i in self:
            if i[0] == key:
                i[:] = func(i)


class SQLQueryInfo:
    """ SQL查询参数。"""
    def __init__(self, params=None, view: 'AbstractSQLView' = None):
        self.select: Union[Set[str], Literal[ALL_COLUMNS]] = ALL_COLUMNS
        self.select_exclude: Set[str] = set()
        self.conditions = QueryConditions()
        self.orders: List[SQLQueryOrder] = []
        self.loadfk: Dict[str, List[Dict[str, object]]] = {}

        if params: self.parse(params)
        if view: self.bind(view)

    @classmethod
    async def build(cls, view: 'AbstractSQLView'):
        info = cls()
        params = None
        post = await view.post_data()
        if post:
            params = post.get('$query', None)

        if not params:
            params = view.params

        info.parse(params)
        info.bind(view)
        return info

    def set_orders(self, orders: List[SQLQueryOrder]):
        assert isinstance(orders, list)
        for i in orders:
            assert isinstance(i, SQLQueryOrder)
        self.orders = orders.copy()

    @staticmethod
    def parse_order(text):
        """
        :param text: order=id.desc, xxx.asc
        :return: [
            [<column>, asc|desc|default],
            [<column2>, asc|desc|default],
        ]
        """
        orders = []
        for i in map(str.strip, text.split(',')):
            items = i.split('.', 2)

            if len(items) == 1: column, order = items[0], 'default'
            elif len(items) == 2: column, order = items
            else: raise InvalidParams("Invalid order syntax")

            order = order.lower()
            if order not in ('asc', 'desc', 'default'):
                raise InvalidParams('Invalid order mode: %s' % order)

            if order != 'default':
                orders.append(SQLQueryOrder(column, order))
        return orders

    def set_select(self, items):
        if items == ALL_COLUMNS:
            self.select = ALL_COLUMNS
        elif isinstance(items, Iterable):
            for i in items:
                assert isinstance(i, str)
            self.select = set(items)
        else:
            raise InvalidParams('Invalid select')

    @classmethod
    def parse_select(cls, text: str) -> Union[Set, Literal[ALL_COLUMNS]]:
        """
        get columns from select text
        :param text: col1, col2
        :return: ALL_COLUMNS or ['col1', 'col2']
        """
        if text == '*':
            return ALL_COLUMNS  # None means ALL
        selected_columns = set(filter(lambda x: x, map(str.strip, text.split(','))))
        if not selected_columns:
            raise InvalidParams("No column(s) selected")
        return selected_columns

    @classmethod
    def parse_load_fk(cls, data: Dict[str, List[Dict[str, object]]]) -> Dict[str, List[Dict[str, object]]]:
        """
        :param data:{
            <column>: role,
            <column2>: role,
            <column>: {
                'role': role,
                'loadfk': { ... },
            },
        :return: {
            <column>: {
                'role': role,
            },
            ...
            <column3>: {
                'role': role,
                'loadfk': { ... },
            },
        }
        """
        default_value_dict = {'role': None, 'as': None, 'table': None, 'loadfk': None}

        def value_normalize_dict(value):
            def check(k, v):
                if k == 'role': return isinstance(v, str)
                if k == 'as': return isinstance(v, str)
                if k == 'table': return isinstance(v, str)
                if k == 'loadfk': return isinstance(v, dict)

            valid = {k: v for k, v in value.items() if check(k, v)}
            if not valid: return default_value_dict.copy()
            if 'loadfk' in valid and valid['loadfk']:
                valid['loadfk'] = cls.parse_load_fk(valid['loadfk'])
            for k, v in default_value_dict.items():
                valid.setdefault(k, v)
            return valid

        def value_normalize(value, no_list=True):
            if value is None:
                return default_value_dict.copy()
            elif not no_list and isinstance(value, List):
                # <column>: [value1, value2, ...]
                return list(map(value_normalize, value))
            elif isinstance(value, str):
                # <column>: role
                val = default_value_dict.copy()
                val['role'] = value
                return val
            elif isinstance(value, Mapping):
                # {'role': <str>, 'as': <str>, ...}
                return value_normalize_dict(value)
            else:
                raise InvalidParams('Invalid syntax for "loadfk": %s' % value)

        # 对全部项进行检查
        new_data = {}
        if not isinstance(data, dict):
            raise InvalidParams('Invalid syntax for "loadfk": %s' % data)
        for k, v in data.items():
            nv = value_normalize(v, False)
            new_data[k] = nv if isinstance(nv, List) else [nv]
        return new_data

    @classmethod
    def check_condition_and_format(cls, val: Iterable) -> List:
        """
        检查条件语句，并将其格式化为可用状态
        :param val:
        :return:
        """
        field_name, op, value = val
        if not isinstance(op, SQL_OP):
            if op not in SQL_OP.txt2op:
                raise SQLOperatorInvalid(op, 'The condition is illegal: %s' % val)
            else:
                op = SQL_OP.txt2op.get(op)
        return [field_name, op, value]

    def add_condition(self, field_name, op, value):
        """
        Add a query condition and validate it.
        raise ParamsException if failed.
        self.view required
        :param field_name:
        :param op:
        :param value:
        :return: None
        """
        cond = self.check_condition_and_format((field_name, op, value))
        self.conditions.append(cond)

    def parse_then_add_condition(self, field_name, op_name, value):
        if op_name not in SQL_OP.txt2op:
            raise SQLOperatorInvalid(op_name)
        op = SQL_OP.txt2op.get(op_name)
        if op in (SQL_OP.IN, SQL_OP.NOT_IN, SQL_OP.CONTAINS, SQL_OP.CONTAINS_ANY):
            try:
                # 强制 json.loads() 右值，符合 parameters 的一般情况
                value = json.loads(value)
            except (TypeError, json.JSONDecodeError):
                raise InvalidParams('The right value of "in" condition must be serialized json string: %s' % value)
        self.add_condition(field_name, op, value)

    def clear_condition(self):
        self.conditions.clear()

    def parse(self, params):
        for key, value in params.items():
            # xxx.{op}
            info = key.split('.', 1)

            field_name = info[0]

            if field_name.startswith('$'):
                continue
            elif field_name == 'order':
                self.orders = self.parse_order(value)
                continue
            elif field_name == 'select':
                self.select = self.parse_select(value)
                continue
            elif field_name == '-select':
                self.select_exclude = self.parse_select(value)
                continue
            elif field_name == 'loadfk':
                try:
                    value = json.loads(value)  # [List, Dict[str, str]]
                except (json.JSONDecodeError, TypeError):
                    raise InvalidParams('Invalid json syntax for "loadfk": %s' % value)
                self.loadfk = self.parse_load_fk(value)
                continue

            op = info[1] if len(info) > 1 else 'eq'
            self.parse_then_add_condition(field_name, op, value)

    def check_query_permission(self, view: "AbstractSQLView"):
        user = view.current_user if view.can_get_user else None
        self.check_query_permission_full(user, view.table_name, view.ability, view)

    def check_query_permission_full(self, user: "BaseUser", table: str, ability: "Ability", view: "AbstractSQLView", ignore_error=True):
        from .permission import A

        # QUERY 权限检查
        # QUERY 的特殊之处在于即使没有查询条件也会查出数据
        checking_columns = set()
        checking_columns_qex = set()

        if self.conditions:
            # 按照目前的设计，存在condition的情况下才会检查condition的权限
            is_qex_cond = lambda x: x[1] == SQL_OP.ILIKE or x[1] == SQL_OP.LIKE
            is_q_cond = lambda x: not is_qex_cond(x)

            for c in self.conditions:
                field_name, op, value = c
                if is_qex_cond(c):
                    checking_columns_qex.add(field_name)
                else:
                    checking_columns.add(field_name)

            def condition_filter(available_columns: Set, skip_func):
                new_conditions = []
                for i in self.conditions:
                    if skip_func(i):
                        # 如果不是要检查的列，那么直接填入
                        new_conditions.append(i)
                    else:
                        # 如果是的话，将不在许可列中的条件剔除掉
                        if i[0] in available_columns:
                            new_conditions.append(i)

                self.conditions[:] = new_conditions

            def do_check(cs: Set, skip_func, action):
                if cs:
                    new_columns = ability.can_with_columns(user, action, table, cs)

                    if not ignore_error:
                        if len(cs) != len(new_columns):
                            raise PermissionDenied("These columns has no permission to %s: %r of %r" % (action, cs - new_columns, table))

                    condition_filter(new_columns, skip_func)

            do_check(checking_columns, is_qex_cond, A.QUERY)
            do_check(checking_columns_qex, is_q_cond, A.QUERY_EX)

            # 所有查询条件都被权限机制清空，被认为是出乎意料的结果，所以抛出异常
            # 否则用户会得到一个无条件查询出的数据。
            if not self.conditions:
                raise PermissionDenied("No column had permission to %s: %r of %r" % (
                    A.QUERY, checking_columns.union(checking_columns_qex), table))

        # READ 权限检查，通不过时将其过滤
        checking_columns = self.loadfk.keys()  # 外键过滤
        new_loadfk = ability.can_with_columns(user, A.READ, table, checking_columns)
        self.loadfk = dict_filter(self.loadfk, new_loadfk)

        new_select = ability.can_with_columns(user, A.READ, table, self.select)  # select 过滤
        self.set_select(new_select)

        # 设置附加条件
        ability.setup_extra_query_conditions(user, table, self, view)

    def bind(self, view: "AbstractSQLView"):
        def check_column_exists(column):
            if column is PRIMARY_KEY:
                return
            if column not in view.fields:
                raise ColumnNotFound({column: [ERR_TEXT_ROGUE_FIELD]})

        # select check
        def show_select(s: Union[Literal[ALL_COLUMNS], Set]) -> Set:
            if s is ALL_COLUMNS:
                return view.fields.keys()
            else:
                for field_name in s:
                    check_column_exists(field_name)
                if PRIMARY_KEY in s:
                    s.remove(PRIMARY_KEY)
                    s.add(view.primary_key)
                return s

        # select = normal select - reverse select
        self.select = show_select(self.select) - show_select(self.select_exclude)

        # where convert
        for i in self.conditions:
            field_name, op, value = i
            check_column_exists(field_name)

            if field_name == PRIMARY_KEY:
                i[0] = field_name = view.primary_key

        # permission check
        # 是否需要一个 order 权限？
        if view.ability:
            self.check_query_permission(view)

        # where check
        for i in self.conditions:
            field_name, op, value = i
            check_column_exists(field_name)
            if field_name == PRIMARY_KEY:
                i[0] = field_name = view.primary_key

            field_type: BaseType = view.fields[field_name]

            # 此处会进行类型转换和校验
            # 一个重点是，因为之前的 check_query_permission 会调用很多回调，他们输入的值一般认为是符合类型的最终值，
            # 而又有可能原始的值来自于 parameters，他们是文本！这引发了下面TODO的两个连带问题
            def conv(x):
                nonlocal field_type
                if op in (SQL_OP.CONTAINS, SQL_OP.CONTAINS_ANY):
                    assert isinstance(field_type, ListType), 'contains only works with ArrayField'
                    field_type2 = field_type.field
                else:
                    field_type2 = field_type

                # TODO: 这里的 null 感觉有很大问题，或许应该明确一下字符串"null"和null？
                if x in ('null', None):
                    return None
                else:
                    return field_type2.validate(x)

            try:
                # 注：外键的类型会是其指向的类型，这里不用额外处理
                # TODO: Iterable 似乎不是一个靠谱的类型？这样想对吗？
                if op in (SQL_OP.CONTAINS, SQL_OP.CONTAINS_ANY):
                    assert isinstance(field_type, ListType), 'contains only works with ArrayField'

                if op in (SQL_OP.IN, SQL_OP.NOT_IN, SQL_OP.CONTAINS, SQL_OP.CONTAINS_ANY):
                    assert isinstance(value, Iterable)
                    i[2] = list(map(conv, value))
                else:
                    i[2] = conv(value)

            except ConversionError as e:
                raise InvalidParams({field_name: e.to_primitive()})
            except Exception as e:
                # 这里本来设计了一个 condition name，但是觉得会对整体性造成破坏，就不用了
                # cond_name = '%s.%s' % (field_name, op.value[0])
                raise InvalidParams({field_name: ["Can not convert to data type of the field"]})

        # order check
        for i, od in enumerate(self.orders):
            check_column_exists(od.column)
            if od.column == PRIMARY_KEY:
                self.orders[i] = view.primary_key

        # foreign key check
        app = view.app

        def check_loadfk_data(the_view, data):
            if PRIMARY_KEY in data:
                data[the_view.primary_key] = data[PRIMARY_KEY]
                del data[PRIMARY_KEY]

            for field_name, values_lst in data.items():
                # field_name: [{'role': role, 'loadfk': {...}}]
                # field_name: [{'as': 's24h', 'table': 's24', 'role': role}]

                # 检查列是否存在
                if field_name not in the_view.fields:
                    raise ColumnNotFound({field_name: [ERR_TEXT_ROGUE_FIELD]})

                # 检查列是否是合法的外键列
                fks = the_view.foreign_keys.get(field_name, None)
                if not fks: raise ColumnIsNotForeignKey({field_name: [ERR_TEXT_COLUMN_IS_NOT_FOREIGN_KEY]})

                for values in values_lst:
                    # 检查是否采用别名将外键对应到特定表上
                    if values['table']:
                        if values['table'] not in the_view.foreign_keys_table_alias:
                            raise ResourceException('Foreign key not match the table: %r -> %r' % (field_name, values['table']))
                        fk = the_view.foreign_keys_table_alias[values['table']]
                        values['table'] = fk.rel_table
                    else:
                        fk = fks[0]  # 取第一个结果（即默认外键）
                        values['table'] = fk.rel_table

                    # 检查对应的表是否存在
                    if fk.rel_table not in app.tables:
                        raise TableNotFound("Foreign key refer to a table not exists: %r -> %r" % (field_name, fk.rel_table))

                    # 检查对应的表的角色是否存在
                    if values['role'] not in app.permission.roles:
                        raise InvalidRole('%s of %s' % (values['role'], fk.rel_table))

                    # 递归外键读取
                    if values['loadfk']:
                        check_loadfk_data(app.tables[fk.rel_table], values['loadfk'])

        if self.loadfk:
            check_loadfk_data(view, self.loadfk)


class SQLValuesToWrite(dict):
    def __init__(self, raw_data=None, view: 'AbstractSQLView'=None, action=None, records=None):
        super().__init__()
        self.returning = False
        self.view = view

        # design of incr/desc:
        # 1. incr/desc/normal_set can't be appear in the same time
        # 2. incr/desc use self to store data
        self.incr_fields = set()
        self.decr_fields = set()
        self.set_add_fields = set()
        self.set_remove_fields = set()
        self.array_append = set()
        self.array_remove = set()

        if raw_data:
            assert isinstance(raw_data, Mapping)
            self.parse(raw_data)
            if view: self.bind(view, action, records)

    def parse(self, post_data: MultiDict):
        self.clear()
        if isinstance(post_data, dict):
            post_data = MultiDict(post_data)

        for k, v in post_data.items():
            # 提交多个相同值，等价于提交一个数组（用于formdata和urlencode形式）
            v_all = post_data.getall(k)
            if len(v_all) > 1:
                v = v_all

            if k.startswith('$'):
                continue
            elif k == 'returning':
                self.returning = True
                continue
            elif '.' in k:
                # TODO: 不允许 incr 和普通赋值同时出现
                k, op = k.rsplit('.', 1)
                if op == 'incr':
                    self.incr_fields.add(k)
                elif op == 'decr':
                    self.decr_fields.add(k)
                elif op == 'set_add':
                    self.set_add_fields.add(k)
                elif op == 'set_remove':
                    self.set_remove_fields.add(k)
                # elif op == 'array_append':
                #     self.array_append.add(k)
                # elif op == 'array_remove':
                #    self.array_remove.add(k)

            self[k] = v

    def check_insert_permission(self, user: "BaseUser", table: str, ability: "Ability"):
        from .permission import A
        columns = self.keys()
        logger.debug('request permission as %r: [%s] of table %r, columns: %s' % (ability.role, A.CREATE, table, columns))
        is_empty_input = not columns

        # 如果插入数据项为空，那么用户应该至少有一个列的插入权限
        if is_empty_input:
            if self.view:
                columns = self.view.fields.keys()

        available = ability.can_with_columns(user, A.CREATE, table, columns)
        if not available: raise PermissionDenied()
        dict_filter_inplace(self, available)

        valid = ability.can_with_columns(user, A.CREATE, table, available)

        if is_empty_input:
            if len(valid) <= 0:
                logger.debug("request permission failed as %r. request / valid: %r, %r" % (ability.role, list(self.keys()), valid))
                raise PermissionDenied()
        else:
            if len(valid) != len(self):
                logger.debug("request permission failed as %r. request / valid: %r, %r" % (ability.role, list(self.keys()), valid))
                raise PermissionDenied()

        logger.debug("request permission successed as %r: %r" % (ability.role, list(self.keys())))

    def check_update_permission(self, user: "BaseUser", table: str, ability: "Ability", records):
        from .permission import A
        columns = self.keys()
        logger.debug('request permission as %r: [%s] of table %r, columns: %s' % (ability.role, A.WRITE, table, columns))
        available = ability.can_with_columns(user, A.WRITE, table, columns)

        if not available:
            raise PermissionDenied()

        dict_filter_inplace(self, available)

        for record in records:
            valid = ability.can_with_record(user, A.WRITE, record, available=available)
            if len(valid) != len(self):
                logger.debug("request permission failed as %r. request / valid: %r, %r" % (ability.role, list(self.keys()), valid))
                raise PermissionDenied()

        logger.debug("request permission successed as %r: %r" % (ability.role, list(self.keys())))

    def check_write_permission(self, view: "AbstractSQLView", action, records=None):
        from .permission import A
        user = view.current_user if view.can_get_user else None
        if action == A.WRITE:
            self.check_update_permission(user, view.table_name, view.ability, records)
        elif action == A.CREATE:
            self.check_insert_permission(user, view.table_name, view.ability)
        else:
            raise SlimException("Invalid action to write: %r" % action)

    def bind(self, view: "AbstractSQLView", action=None, records=None):
        """
        建立写入值与 view 的联系。
        由于这之后还有一个 before_insert / before_update 的过程，所以这里不尽量抛出异常，只是在装入 values 前把不合规的过滤
        :param view:
        :param action:
        :param records:
        :return:
        """
        from .permission import Ability, A

        # 1. 融合before_update / before_insert 的校验器，走一次过滤
        if action == A.WRITE:
            func = view.before_update
        else:
            func = view.before_insert

        meta = get_meta(func)
        model_cls = schematics_model_merge(view.data_model, *meta.va_write_value_lst)

        try:
            # 初次bind应该总在before_update / before_insert之前
            # 因此进行带partial的校验（即忽略required=True项，因为接下来还会有补全的可能）
            m = model_cls(self, strict=False, validate=True, partial=True)
            data = m.to_native()

            for k in self:
                self[k] = data.get(k)

            self.incr_fields.intersection_update(self.keys())
            self.decr_fields.intersection_update(self.keys())
            self.set_add_fields.intersection_update(self.keys())
            self.set_remove_fields.intersection_update(self.keys())
            self.array_append.intersection_update(self.keys())
            self.array_remove.intersection_update(self.keys())
        except DataError as e:
            raise InvalidPostData(e.to_primitive())
        # 没捕获 TypeError

        dict_filter_inplace(self, view.fields.keys())

        # 过滤后空 post 不代表无意义，因为插入值可能在 before_insert 中修改
        # if len(self) == 0:
        #     raise InvalidPostData('Invalid post values for table: %s' % view.table_name)

        # 同样，空值不做检查，因为会抛出无权访问
        if action and len(self):
            self.check_write_permission(view, action, records)

    def validate_before_execute_insert(self, view: "AbstractSQLView"):
        # 在执行insert之前，需要校验插入项是否完整（所有require项存在）
        try:
            view.data_model(self, strict=False, validate=True, partial=False)
        except DataError as e:
            raise InvalidPostData(e.to_primitive())
