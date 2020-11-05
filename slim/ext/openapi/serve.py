import json
from posixpath import join as urljoin
from typing import TYPE_CHECKING

from slim.base.web import Response
from slim.ext.openapi.main import get_openapi

if TYPE_CHECKING:
    from slim import Application
    from slim.base.view import RequestView


def doc_serve(app: 'Application', crud):
    spec_url = urljoin(app.mountpoint, '/openapi.json')

    @app.route.get(spec_url)
    async def openapi(request: 'RequestView'):
        role = request.params.get('role')
        return get_openapi(app, role)

    @app.route.get('/redoc')
    async def redoc(request: 'RequestView'):
        """
        role = request.params.get('role')

        def get_role_spec_url(role):
            if role is None:
                return spec_url
            if role in app.permission.roles:
                my_spec_url_tmpl = f'{spec_url}?role=%s'
                return my_spec_url_tmpl % role
            return spec_url

        def get_query_by_role(role):
            if role is None:
                return ''
            if role in app.permission.roles:
                return '?role=' + role
            return ''

        my_spec_url = get_role_spec_url(role)

        options = ''
        for i in app.permission.roles:
            selected = 'selected ' if role == i else ''
            options += '<option ' + selected + 'value=%r>%s</option>' % (get_query_by_role(i), i or 'visitor')

        change_role_html = '''
<div id="change-role" style="position: fixed; top: 10px; right: 10px; z-index: 100; display: flex; align-items: center;background: white;padding: 4px;border-radius: 1px;">
    <span style="font-size: 14px; margin-right: 5px">切换角色:</span>
    <select onchange="window.location.search=this.value">
        %s
    </select>
</div>''' % options
        """

        change_role_html = ''
        return Response(data='''
<!DOCTYPE html>
<html>
  <head>
    <title>ReDoc</title>
    <!-- needed for adaptive design -->
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">

    <!--
    ReDoc doesn't change outer page styles
    -->
    <style>
      body {
        margin: 0;
        padding: 0;
      }
    </style>
  </head>
  <body>
    <redoc spec-url='%s'></redoc>
    <script src="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js"> </script>
    %s
  </body>
</html>
    ''' % (spec_url, change_role_html), content_type='text/html')
