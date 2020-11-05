# https://github.com/OAI/OpenAPI-Specification/blob/master/versions/3.0.2.md
from copy import deepcopy
from typing import Type, TYPE_CHECKING

from slim.base.types.route_meta_info import RouteInterfaceInfo
from slim.base.types.func_meta import FuncMeta
from slim.base.user import BaseUserViewMixin
from slim.ext.crud_view.inner_interface_name import BuiltinInterface
from slim.utils.schematics_ext import schematics_field_to_schema, schematics_model_to_json_schema, field_metadata_assign

if TYPE_CHECKING:
    from slim import Application

paginate_schema = {
    "type": "object",
    "properties": {
        "cur_page": {
            "type": "integer"
        },
        "prev_page": {
            "type": "integer"
        },
        "next_page": {
            "type": "integer"
        },
        "first_page": {
            "type": "integer"
        },
        "last_page": {
            "type": "integer"
        },
        "page_numbers": {
            "type": "array",
            "example": [1, 2, 3],
            "items": {
                "type": "integer"
            }
        },
        "info": {
            "type": "object",
            "properties": {
                "page_size": {
                    "type": "integer"
                },
                "page_count": {
                    "type": "integer"
                },
                "items_count": {
                    "type": "integer"
                }
            },
            "required": [
                "page_size",
                "page_count",
                "items_count"
            ]
        },
        "items": {
            "type": "array",
            "items": {}
        }
    },
    "required": [
        "cur_page",
        "prev_page",
        "next_page",
        "first_page",
        "last_page",
        "page_numbers",
        "info",
        "items"
    ]
}

std_resp_schema = {
    "type": "object",
    "properties": {
        "code": {
            "type": "number",
            "description": '系统返回值代码，成功为0，失败为非零。  \n参见 https://fy0.github.io/slim/#/quickstart/query_and_modify?id=返回值 '
        },
        "data": {
            "description": "数据项"
        },
        "msg": {
            "type": "string",
            "description": "文本提示信息"
        }
    },
    "required": ["code", "data"]
}


class OpenAPIGenerator:
    def __init__(self, app: 'Application', role):
        self.app = app
        self.role = role

        self.view_info = {}

        self.paths = {}
        self.openapi_file = ''

        self._view_to_path = {}
        self._field_schema_cache = {}

        # self._sql_views_check()
        self._build_paths()
        self._build_main()

    def _schematics_field_to_parameter(self, name, field):
        return field_metadata_assign(field, {
            'name': name,
            'in': 'query',
            'description': '',
            'required': False,
            "schema": self._get_schema_from_schematics_field(field)
        })

    def _get_schema_from_schematics_field(self, field):
        val = self._field_schema_cache.get(field)

        if not val:
            val = schematics_field_to_schema(field)
            self._field_schema_cache[field] = val

        return val

    def _sql_views_check(self):
        app = self.app

        for vi in app.route._views:
            view_cls = vi.view_cls
            is_sql_view = issubclass(view_cls, AbstractSQLView)

            if is_sql_view:
                view_cls: Type[AbstractSQLView]
                available_columns = {}
                ab: Ability = app.permission.roles[self.role]

                for a in A.ALL_EXTRA:
                    available_columns[a] = ab.can_with_columns(None, a, view_cls.table_name, view_cls.fields.keys())

                sql_query_parameters = []
                columns = available_columns[A.QUERY].union(available_columns[A.QUERY_EX])
                for k in columns:
                    field = view_cls.fields[k]
                    info = self._schematics_field_to_parameter(k, field)
                    sql_query_parameters.append(info)

                def get_schema_by_ability(a):
                    _schema = {}

                    for k in available_columns[a]:
                        field = view_cls.fields[k]
                        _schema[k] = self._get_schema_from_schematics_field(field)

                    return _schema

                self.view_info[view_cls] = {
                    'sql_query_parameters': sql_query_parameters,
                    'sql_read_record_schema': get_schema_by_ability(A.READ),
                    'sql_write_schema': get_schema_by_ability(A.UPDATE),
                    'sql_create_schema': get_schema_by_ability(A.CREATE),

                    'sql_cant_write': len(available_columns[A.UPDATE]) == 0,
                    'sql_cant_create': len(available_columns[A.CREATE]) == 0,
                    'sql_cant_delete': len(available_columns[A.DELETE]) == 0,
                }

    def _interface_solve(self, beacon_info: RouteInterfaceInfo, method, parameters, request_body_schema):
        if beacon_info.va_query:
            for k, v in beacon_info.va_query._fields.items():
                parameters.append(self._schematics_field_to_parameter(k, v))

        if method != 'GET':
            if beacon_info.va_post:
                return schematics_model_to_json_schema(beacon_info.va_post)

            if request_body_schema:
                return request_body_schema

    def _build_paths(self):
        from slim.view import CrudView
        paths = {}

        def returning_wrap(items_schema):
            return {
                'oneOf': [
                    {
                        "type": "integer",
                        "description": "影响数据个数(不带returning情况下)",
                    },
                    items_schema
                ]
            }

        for i in self.app.route._funcs_meta:
            path_item_object = {}

            view_cls = i.view_cls
            is_sql_view = issubclass(view_cls, CrudView)
            self._view_to_path.setdefault(view_cls, [])

            for method in i.methods:
                parameters = []
                request_body_schema = {}
                response_schema = deepcopy(std_resp_schema)

                summary = i.summary or i.handler.__name__

                if issubclass(view_cls, BaseUserViewMixin):
                    parameters.append({
                        "name": 'AccessToken',
                        "in": "header",
                        "schema": {
                            "type": "string",
                        }
                    })
                    parameters.append({
                        "name": 'Role',
                        "in": "header",
                        "description": "用于指定当前的用户角色。以不同的角色访问同一个API可能会得到不同的结果。\n举例来说，`admin`权限的用户，可能具有`admin` `user` `visitor`三个角色，在用get接口查看用户数据时，`admin`可能相比`user`多获取了用户最后登录的时间。但`admin`用户可以控制自己在某些情况下只以`user`的身份去取得数据。",
                        "schema": {
                            "type": "string",
                        }
                    })

                def add_returning_header():
                    parameters.append({
                        "name": 'returning',
                        "in": "header",
                        "schema": {},
                        "description": "当存在 returning 时，返回值的data中将是数据对象，否则为影响的记录条数。对`set` `new` `bulk_new`接口有效。",
                    })

                def add_bulk_header():
                    parameters.append({
                        "name": 'bulk',
                        "in": "header",
                        "description": "对`set`和`delete`接口有效，用于批量插入和删除。当`bulk`存在，例如为'true'的时候，接口会对可查询到的全部项起效。 `bulk`还可以是大于零的整数，代表影响的数据项个数。",
                        "schema": {
                            "type": "integer",
                        }
                    })

                # check role require
                meta: FuncMeta = getattr(i.handler, '__meta__', None)
                if meta and meta.interface_roles is not None:
                    if self.role not in meta.interface_roles:
                        continue

                if False:
                    is_builtin = i.builtin_interface
                    # view_info = self.view_info[view_cls]

                    if is_builtin:
                        sql_query = i.va_query
                        sql_post = i.va_post

                        if i.builtin_interface == BuiltinInterface.SET:
                            if view_info['sql_cant_write']:
                                continue
                            add_bulk_header()
                            add_returning_header()
                            request_body_schema = {
                                "type": "object",
                                "properties": view_info['sql_write_schema']
                            }

                        if i.builtin_interface == BuiltinInterface.NEW:
                            if view_info['sql_cant_create']:
                                continue
                            add_returning_header()
                            request_body_schema = {
                                "type": "object",
                                "properties": view_info['sql_create_schema']
                            }

                        if i.builtin_interface == BuiltinInterface.BULK_INSERT:
                            if view_info['sql_cant_create']:
                                continue
                            add_returning_header()
                            request_body_schema = {
                                "type": "object",
                                "properties": {
                                    "items": {
                                        "type": "array",
                                        "description": "数据项",
                                        "items": {
                                            "type": "object",
                                            "properties": view_info['sql_create_schema']
                                        }
                                    }
                                }
                            }

                        if i.builtin_interface == BuiltinInterface.DELETE:
                            if view_info['sql_cant_delete']:
                                continue
                            add_bulk_header()
                            request_body_schema = {
                                "type": "integer",
                                "description": "影响数据个数",
                            }

                        if i.builtin_interface == BuiltinInterface.LIST:
                            parameters.extend([
                                {
                                    "name": "page",
                                    "in": "path",
                                    "description": "",
                                    "required": True,
                                    "schema": {
                                        "type": "number"
                                    }
                                },
                                {
                                    "name": "size",
                                    "in": "path",
                                    "description": "",
                                    "required": False,
                                    "schema": {
                                        "type": "number"
                                    }
                                }
                            ])

                        if sql_query:
                            parameters.extend(view_info['sql_query_parameters'])

                        if i.builtin_interface == BuiltinInterface.LIST:
                            page_info = deepcopy(paginate_schema)
                            page_info["properties"]["items"] = {
                                "type": "array",
                                "description": "数据项",
                                "items": {
                                    "type": "object",
                                    "properties": view_info['sql_read_record_schema']
                                }
                            }
                            response_schema["properties"]["data"] = page_info
                        else:
                            response_schema["properties"]["data"] = returning_wrap({
                                "type": "object",
                                "description": "数据项",
                                "properties": view_info['sql_read_record_schema']
                            })

                request_body_schema = self._interface_solve(i, method, parameters, request_body_schema)

                request_body = {
                    "content": {
                        "application/json": {
                            "schema": request_body_schema
                        }
                    }
                }

                responses = {
                    200: {
                        "description": "Success",
                        "content": {
                            "application/json": {
                                "schema": response_schema
                            }
                        }
                    }
                }

                def get_func_doc(view_cls, interface_name, handler):
                    doc = handler.__doc__
                    if doc: doc = doc.strip()
                    if not doc:
                        for cls in view_cls.mro()[1:]:
                            f = getattr(cls, interface_name, None)
                            if f:
                                doc = f.__doc__
                                if doc: doc = doc.strip()
                                if doc: break

                    return doc or ''

                path = {
                    "tags": [i.view_cls.__name__],
                    "summary": summary,
                    "description": get_func_doc(view_cls, i.handler.__name__, i.handler),
                    "parameters": parameters,
                    "responses": responses
                }

                if i.deprecated:
                    path['deprecated'] = True

                if request_body_schema:
                    path["requestBody"] = request_body

                path_item_object[method.lower()] = path

                self._view_to_path[view_cls].append(path_item_object)
                paths[i.fullpath] = path_item_object

        self.paths = paths

    def _build_main(self):
        from slim.base.view.request_view import RequestView
        doc_info = self.app.doc_info

        self.openapi_file = {
            'openapi': '3.0.2',
            'info': {
                'title': doc_info.title,
                'description': doc_info.description,
                # 'termsOfService': '',  # MUST be url
                'contact': {
                    "name": "API Support",
                    "url": "http://www.example.com/support",
                    "email": "support@example.com"
                },
                # 'license': {}
                'version': '1.0.0'
            },
            'paths': self.paths
        }

        if doc_info.version:
            self.openapi_file['info']['version'] = doc_info.version

        if doc_info.license:
            self.openapi_file['info']['license'] = doc_info.license

        if doc_info.contact:
            self.openapi_file['info']['contact'] = doc_info.contact

        tags = []
        for vi in self.app.route._views + [RequestView._route_info]:
            tag = {
                'name': vi.view_cls.__name__,
                'description': (vi.view_cls.__doc__ or '').strip()
            }

            if vi.tag_display_name is not None:
                tag['x-displayName'] = vi.tag_display_name

            if self._view_to_path.get(vi.view_cls):
                tags.append(tag)

        if doc_info.tags:
            for _, v in doc_info.tags.items():
                tags.append(v)

        self.openapi_file['tags'] = tags

        if doc_info.x_tag_groups:
            tag_groups = []
            for _, v in doc_info.x_tag_groups.items():
                tag_groups.append(v)
            self.openapi_file['x-tagGroups'] = tag_groups

    def get_result(self):
        return self.openapi_file


def get_openapi(app: 'Application', role=None):
    gen = OpenAPIGenerator(app, role)
    return gen.get_result()
