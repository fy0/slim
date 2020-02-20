from posixpath import join as urljoin
from typing import TYPE_CHECKING

from aiohttp import web
from aiohttp.web_request import Request

from slim.ext.openapi.main import get_openapi

if TYPE_CHECKING:
    from slim import Application


def doc_serve(app: 'Application'):
    spec_url = urljoin(app.mountpoint, '/openapi.json')

    @app.route(spec_url, 'GET')
    async def openapi(request):
        role = request.query.get('role')
        return web.json_response(get_openapi(app, role))

    @app.route('/redoc', 'GET')
    async def openapi(request: Request):
        my_spec_url = spec_url
        role = request.query.get('role')

        if role and role in app.permission.roles:
            my_spec_url += '?role=%s' % role

        return web.Response(content_type='text/html',body='''
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
  </body>
</html>
    ''' % my_spec_url)
