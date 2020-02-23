# https://github.com/OAI/OpenAPI-Specification/blob/master/versions/3.0.2.md
from copy import deepcopy
from typing import Type, TYPE_CHECKING

from slim.retcode import RETCODE
from slim.utils.schematics_ext import schematics_field_to_schema

if TYPE_CHECKING:
    from slim import Application
    from slim.base.view import BaseView, AbstractSQLView


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
            "description": '系统返回值代码，成功为0，失败为负数。  \n参见 https://fy0.github.io/slim/#/quickstart/design?id=返回值 '
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

        self._field_schema_cache = {}

        self._sql_views_check()
        self._build_paths()
        self._build_main()

    def _get_schema_from_field(self, field):
        val = self._field_schema_cache.get(field)

        if not val:
            val = schematics_field_to_schema(field)
            self._field_schema_cache[field] = val

        return val

    def _sql_views_check(self):
        from slim.base.permission import Ability, A
        from slim.base.view import BaseView, AbstractSQLView
        app = self.app

        for url, view_cls in app.route.views:
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
                    info = {
                        'name': k,
                        'in': 'query',
                        'description': '',
                        'required': False,
                        "schema": self._get_schema_from_field(field)
                    }
                    sql_query_parameters.append(info)

                def get_schema_by_ability(a):
                    _schema = {}

                    for k in available_columns[a]:
                        field = view_cls.fields[k]
                        _schema[k] = self._get_schema_from_field(field)

                    return _schema

                self.view_info[view_cls] = {
                    'sql_query_parameters': sql_query_parameters,
                    'sql_read_record_schema': get_schema_by_ability(A.READ),
                    'sql_write_schema': get_schema_by_ability(A.WRITE),
                    'sql_create_schema': get_schema_by_ability(A.CREATE),

                    'sql_cant_write': len(available_columns[A.WRITE]) == 0,
                    'sql_cant_delete': len(available_columns[A.DELETE]) == 0,
                    'sql_cant_create': len(available_columns[A.CREATE]) == 0,
                }

    def _build_paths(self):
        from slim.base.view import BaseView, AbstractSQLView
        paths = {}

        for i in self.app.route._beacons.values():
            path_item_object = {}

            view_cls = i.view_cls
            is_sql_view = issubclass(view_cls, AbstractSQLView)

            for method in i['route']['method']:
                raw = i['route']['raw']
                relpath = i['route']['relpath']
                need_response = method == 'POST'

                parameters = []
                request_body_schema = {}
                response_schema = deepcopy(std_resp_schema)

                summary = raw.get('summary') or i['name']

                if is_sql_view:
                    is_inner_interface = raw.get('_sql')
                    view_info = self.view_info[view_cls]

                    if is_inner_interface:
                        sql_query = raw['_sql'].get('query')
                        sql_post = raw['_sql'].get('post')
                        inner_name = raw['inner_name']

                        if inner_name == 'set':
                            if view_info['sql_cant_write']:
                                continue
                            request_body_schema = {
                                "type": "object",
                                "properties": view_info['sql_write_schema']
                            }

                        if inner_name == 'delete':
                            if view_info['sql_cant_delete']:
                                continue
                            request_body_schema = {
                                "type": "object",
                                "properties": view_info['sql_delete_schema']
                            }

                        if inner_name == 'new':
                            if view_info['sql_cant_create']:
                                continue
                            request_body_schema = {
                                "type": "object",
                                "properties": view_info['sql_create_schema']
                            }

                        is_list = raw['inner_name'] in {'list', 'list_size'}

                        if raw['inner_name'] == 'list':
                            parameters.extend([
                                {
                                    "name": "page",
                                    "in": "path",
                                    "description": "",
                                    "required": True,
                                    "schema": {
                                        "type": "number"
                                    }
                                }
                            ])

                        if raw['inner_name'] == 'list_size':
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
                                    "required": True,
                                    "schema": {
                                        "type": "number"
                                    }
                                }
                            ])

                        if sql_query:
                            parameters.extend(view_info['sql_query_parameters'])

                        if is_list:
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
                            response_schema["properties"]["data"] = {
                                "type": "object",
                                "description": "数据项",
                                "properties": view_info['sql_read_record_schema']
                            }

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

                path = {
                    "tags": [i.view_cls.__name__],
                    "summary": summary,
                    "description": (i['handler'].__doc__ or '').strip(),
                    "parameters": parameters,
                    "responses": responses
                }

                if need_response and request_body_schema:
                    path["requestBody"] = request_body

                path_item_object[method.lower()] = path

            paths[i['route']['fullpath']] = path_item_object

        self.paths = paths

    def _build_main(self):
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

    def get_result(self):
        return self.openapi_file


def get_openapi(app: 'Application', role=None):
    gen = OpenAPIGenerator(app, role)
    return gen.get_result()
