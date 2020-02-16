# https://github.com/OAI/OpenAPI-Specification/blob/master/versions/3.0.2.md
from typing import Type, TYPE_CHECKING

if TYPE_CHECKING:
    from slim import Application
    from slim.base.view import BaseView, AbstractSQLView


def get_openapi(app: 'Application'):
    from slim.base.view import AbstractSQLView
    paths = {}

    for i in app.route._beacons.values():
        path_item_object = {}

        for method in i['route']['method']:
            summary = i['name']
            relpath = i['route']['relpath']
            table_query = False
            table_post_data = False

            parameters = []
            request_body = {
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                            },
                        }
                    }
                }
            }

            if issubclass(i['view'], AbstractSQLView):

                if method == 'GET':
                    if relpath == 'get':
                        summary = '取得单项'
                        table_query = True
                    elif relpath == 'list/{page}':
                        summary = '取得列表'
                        table_query = True
                    elif relpath == 'list/{page}/{size}':
                        summary = '取得列表(自定义分页大小)'
                        table_query = True

                elif method == 'POST':
                    if relpath == 'set':
                        summary = '存入'
                        table_query = True
                        table_post_data = True
                    elif relpath == 'new':
                        summary = '新建'
                        table_post_data = True
                    elif relpath == 'delete':
                        summary = '删除'
                        table_query = True
                        table_post_data = True

                if table_query:
                    cls: Type['AbstractSQLView'] = i['view']

                    for k, v in cls.fields.items():
                        parameters.append({
                            'name': k,
                            'in': 'query',
                            'description': '',
                            'required': False
                        })

                if table_post_data:
                    post_values = {}
                    cls: Type['AbstractSQLView'] = i['view']

                    for k, v in cls.fields.items():
                        post_values[k] = {
                            'description': '',
                            'required': False,
                            "type": "string"
                        }

                    request_body['content']['application/json']['schema']['properties'] = post_values

            path_item_object[method.lower()] = {
                'tags': [i['view'].__name__],
                'summary': summary,
                'description': i['handler'].__doc__,
                'parameters': parameters,
                'requestBody': request_body
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