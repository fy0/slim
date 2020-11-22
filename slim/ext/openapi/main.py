# https://github.com/OAI/OpenAPI-Specification/blob/master/versions/3.0.2.md
from collections import OrderedDict
from copy import deepcopy
from typing import Type, TYPE_CHECKING

from slim.base.types.route_meta_info import RouteInterfaceInfo
from slim.base.types.func_meta import FuncMeta
from slim.base.user import BaseUserViewMixin
from slim.ext.crud_view.inner_interface_name import BuiltinCrudInterface
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
}


class OpenAPIGenerator:
    def __init__(self, app: 'Application', role):
        self.app = app
        self.role = role

        self.view_schema_info = {}

        self.paths = {}
        self.openapi_file = ''

        self._view_to_path = {}
        self._field_schema_cache = {}

        self._crud_view_check()
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

    def _crud_view_check(self):
        from slim.view import CrudView
        from pycrud.crud.base_crud import BaseCrud
        from pycrud.permission import RoleDefine
        from pycrud.permission import A

        for vi in self.app.route._views:
            view_cls = vi.view_cls
            is_crud_view = issubclass(view_cls, CrudView)

            if is_crud_view:
                view_cls: Type[CrudView]
                rd: RoleDefine = view_cls.crud.permission.get(self.role)
                dict_filter_by_set = lambda d, s: {k: v for k, v in d.items() if k in s}

                avail_query = rd.get_perm_avail(view_cls.model, A.QUERY)
                avail_create = rd.get_perm_avail(view_cls.model, A.CREATE)
                avail_read = rd.get_perm_avail(view_cls.model, A.READ)
                avail_update = rd.get_perm_avail(view_cls.model, A.UPDATE)

                schemas = view_cls.model.schema()

                schema_query = []
                for k, v in schemas['properties'].items():
                    if k in avail_query:
                        schema_query.append({
                            'name': k + '.{op}',
                            'in': 'query',
                            'schema': v,
                            'description': v['title'],
                            'required': False,
                        })

                schema_create = schemas.copy()
                schema_create['properties'] = dict_filter_by_set(schemas['properties'], avail_create)

                schema_read = schemas.copy()
                schema_read['properties'] = dict_filter_by_set(schemas['properties'], avail_read)

                schema_update = schemas.copy()
                schema_update['properties'] = dict_filter_by_set(schemas['properties'], avail_update)
                schema_update['required'] = []

                self.view_schema_info[view_cls] = {
                    'schema': schemas,
                    'query': schema_query,
                    'create': schema_create,
                    'read': schema_read,
                    'update': schema_update,

                    'can_create': len(avail_create) > 0,
                    'can_read': len(avail_read) > 0,
                    'can_update': len(avail_update) > 0,
                    'can_delete': rd.can_delete(view_cls.model),
                }


    def _interface_solve(self, beacon_info: RouteInterfaceInfo, method, parameters, request_body_schema):
        if beacon_info.va_query:
            for k, v in beacon_info.va_query._fields.items():
                parameters.append(self._schematics_field_to_parameter(k, v))

        if beacon_info.va_post:
            return schematics_model_to_json_schema(beacon_info.va_post)

        if request_body_schema:
            return request_body_schema

    def _build_paths(self):
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
            i: RouteInterfaceInfo
            path_item_object = {}

            view_cls = i.view_cls
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
                        "description": "访问令牌",
                        "schema": {
                            "type": "string",
                        }
                    })
                    parameters.append({
                        "name": 'role',
                        "in": "header",
                        "description": "指定当前的用户角色。以不同的角色访问同一API可能会得到不同的结果。",
                        "schema": {
                            "type": "string",
                        }
                    })

                def add_returning_header():
                    parameters.append({
                        "name": 'returning',
                        "in": "header",
                        "schema": {},
                        "description": "当存在 returning 时，返回值的data中将是数据对象，否则为影响的记录条数。对`insert` `bulk_insert` `update`接口有效。",
                    })

                def add_bulk_header():
                    parameters.append({
                        "name": 'bulk',
                        "in": "header",
                        "description": "用于批量插入、更新和删除。当`bulk`存在，例如为'true'的时候，接口会对可查询到的全部项起效。 `bulk`还可以是大于零的整数，代表影响的数据项个数。",
                        "schema": {
                            'oneOf': [
                                {"type": "integer"},
                                {"type": "boolean"},
                            ]
                        }
                    })

                # check role require
                meta: FuncMeta = getattr(i.handler, '__meta__', None)
                if meta and meta.interface_roles is not None:
                    if self.role not in meta.interface_roles:
                        continue

                bultin_interface = i.builtin_interface

                if bultin_interface:
                    schema_info = self.view_schema_info[view_cls]

                    # Create
                    if bultin_interface == BuiltinCrudInterface.INSERT:
                        request_body_schema = schema_info['create']

                    # Read
                    elif bultin_interface == BuiltinCrudInterface.GET:
                        response_schema = schema_info['read']
                    elif bultin_interface == BuiltinCrudInterface.LIST:
                        response_schema = {
                            "type": "array",
                            "description": "数据项",
                            "items": {
                                "type": "object",
                                "properties": schema_info['read']['properties']
                            }
                        }
                    elif bultin_interface == BuiltinCrudInterface.LIST_PAGE:
                        page_info = deepcopy(paginate_schema)
                        page_info["properties"]["items"] = {
                            "type": "array",
                            "description": "数据项",
                            "items": {
                                "type": "object",
                                "properties": schema_info['read']['properties']
                            }
                        }
                        response_schema = page_info

                    # Update
                    elif bultin_interface == BuiltinCrudInterface.UPDATE:
                        if not schema_info['can_update']:
                            continue
                        request_body_schema = schema_info['update']

                    # Delete
                    elif bultin_interface == BuiltinCrudInterface.DELETE:
                        if not schema_info['can_update']:
                            continue

                    # common query
                    if bultin_interface not in (BuiltinCrudInterface.INSERT, BuiltinCrudInterface.BULK_INSERT):
                        parameters.extend(schema_info['query'])
                        _schema = {
                            "type": "object",
                            "properties": {
                                '$query': {
                                    "type": "object",
                                    "description": '查询条件除了写在请求query里，还可以写在这里。同时存在时取$query优先'
                                }
                            }
                        }
                        if request_body_schema:
                            request_body_schema['properties'].update(_schema['properties'])
                        else:
                            request_body_schema = _schema

                    # common response
                    if bultin_interface in (BuiltinCrudInterface.INSERT, BuiltinCrudInterface.BULK_INSERT, BuiltinCrudInterface.UPDATE, BuiltinCrudInterface.DELETE):
                        response_schema = {
                            "type": "array",
                            "description": "ID列表",
                            "items": {
                                "type": schema_info['schema']['properties']['id']['type'],
                                "examples": [1001, 1002, 1003]
                            }
                        }

                    # returning header for insert bulk_insert update
                    if bultin_interface in (BuiltinCrudInterface.INSERT, BuiltinCrudInterface.BULK_INSERT, BuiltinCrudInterface.UPDATE):
                        add_returning_header()

                    # bulk header for update bulk_insert update delete
                    if bultin_interface in (BuiltinCrudInterface.BULK_INSERT, BuiltinCrudInterface.UPDATE, BuiltinCrudInterface.DELETE):
                        add_bulk_header()

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
                paths[i] = path_item_object

        bi_map = {
            BuiltinCrudInterface.INSERT: '~1',
            BuiltinCrudInterface.BULK_INSERT: '~11',
            BuiltinCrudInterface.GET: '~2',
            BuiltinCrudInterface.LIST: '~21',
            BuiltinCrudInterface.LIST_PAGE: '~22',
            BuiltinCrudInterface.UPDATE: '~3',
            BuiltinCrudInterface.DELETE: '~4'
        }

        def cmp(i):
            # 使预设函数排在靠后位置，且顺序固定
            info: RouteInterfaceInfo = i[0]
            return bi_map.get(info.builtin_interface, info.fullpath)

        paths_final = OrderedDict(sorted(paths.items(), key=cmp))
        self.paths = {k.fullpath: v for k, v in paths_final.items()}

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

        # generate tags by view name
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
