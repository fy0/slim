# https://github.com/OAI/OpenAPI-Specification/blob/master/versions/3.0.2.md
from copy import deepcopy
from typing import Type, TYPE_CHECKING
from slim.utils.schematics_ext import schematics_field_to_schema

if TYPE_CHECKING:
    from slim import Application
    from slim.base.view import BaseView, AbstractSQLView


std_resp_schema = {
    "type": "object",
    "properties": {
        "code": {
            'type': 'number'
        },
        "data": {
            "type": "object",
            "properties": {
            }
        },
        "msg": {
            "type": "string"
        }
    },
}


class OpenAPIGenerator:
    def __init__(self, app: 'Application', role):
        self.app = app
        self.role = role

        self.view_info = {}

    def _sql_views_check(self):
        from slim.base.permission import Ability, A
        app = self.app

        for url, view_cls in app.route.views:
            is_sql_view = issubclass(view_cls, AbstractSQLView)

            if is_sql_view:
                sql_query_parameters = []
                sql_resp_schema = deepcopy(std_resp_schema)

                view_cls: Type[AbstractSQLView]
                available_columns = {}
                ab: Ability = app.permission.roles[self.role]

                for a in A.ALL_EXTRA:
                    available_columns[a] = ab.can_with_columns(None, a, view_cls.table_name, view_cls.fields.keys())

                columns = available_columns[A.QUERY].union(available_columns[A.QUERY_EX])
                for k in columns:
                    field = view_cls.fields[k]
                    info = {
                        'name': k,
                        'in': 'query',
                        'description': '',
                        'required': False,
                        "schema": schematics_field_to_schema(field)
                    }
                    sql_query_parameters.append(info)

                _resp_schema = {}
                columns = available_columns[A.READ]
                for k in columns:
                    field = view_cls.fields[k]
                    _resp_schema[k] = schematics_field_to_schema(field)

                sql_resp_schema["properties"]["data"] = {
                    "type": "object",
                    "properties": _resp_schema
                }

                self.view_info[view_cls] = {
                    'sql_query_parameters': sql_query_parameters,
                    'sql_read_record_schema': _resp_schema,
                    'sql_write_schema': None,
                    'sql_insert_schema': None,
                }


def get_openapi(app: 'Application', role=None):
    from slim.base.view import AbstractSQLView
    from slim.base.permission import Ability, A
    paths = {}

    for i in app.route._beacons.values():
        path_item_object = {}

        view_cls = i['view']
        is_sql_view = issubclass(view_cls, AbstractSQLView)

        sql_query_parameters = []
        sql_resp_schema = deepcopy(std_resp_schema)

        if is_sql_view:
            view_cls: Type[AbstractSQLView]
            available_columns = {}
            ab: Ability = app.permission.roles[role]

            for a in A.ALL_EXTRA:
                available_columns[a] = ab.can_with_columns(None, a, view_cls.table_name, view_cls.fields.keys())

            columns = available_columns[A.QUERY].union(available_columns[A.QUERY_EX])
            for k in columns:
                field = view_cls.fields[k]
                info = {
                    'name': k,
                    'in': 'query',
                    'description': '',
                    'required': False,
                    "schema": schematics_field_to_schema(field)
                }
                sql_query_parameters.append(info)

            _resp_schema = {}
            columns = available_columns[A.READ]
            for k in columns:
                field = view_cls.fields[k]
                _resp_schema[k] = schematics_field_to_schema(field)

            sql_resp_schema["properties"]["data"] = {
                "type": "object",
                "properties": _resp_schema
            }

        for method in i['route']['method']:
            summary = i['name']
            relpath = i['route']['relpath']

            parameters = []
            response_schema = std_resp_schema.copy()

            request_body = {
                "content": {
                    "application/json": {
                        "schema": response_schema
                    }
                }
            }

            if is_sql_view:
                raw = i['route']['raw']
                is_inner_interface = raw.get('_sql')

                if is_inner_interface:
                    summary = raw.get('summary') or summary
                    sql_query = raw['_sql'].get('query')
                    sql_post = raw['_sql'].get('post')

                    if sql_query:
                        parameters.extend(sql_query_parameters)

                    if sql_post:
                        response_schema = sql_resp_schema

                        post_values = {}
                        cls: Type['AbstractSQLView'] = i['view']

                        for k, v in cls.fields.items():
                            post_values[k] = {
                                'description': '',
                                'required': False,
                                "type": "string"
                            }

                        request_body['content']['application/json']['schema']['properties'] = post_values

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

            path_item_object[method.lower()] = {
                "tags": [i['view'].__name__],
                "summary": summary,
                "description": i['handler'].__doc__,
                "parameters": parameters,
                "requestBody": request_body,
                "responses": responses
            }

        paths[i['route']['fullpath']] = path_item_object

    return {
        'openapi': '3.0.2',
        'info': {
            'title': 'slim application',
            'description': '',
            # 'termsOfService': '',  # MUST be url
            'contact': {
                "name": "API Support",
                "url": "http://www.example.com/support",
                "email": "support@example.com"
            },
            # 'license': {}
            'version': '1.0.0'
        },
        'paths': paths
    }
