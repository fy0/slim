# 接收上传的文件

以`content-type: multipart/formdata`格式提交的请求，使用 `view.post_data()`，其中的文件会被读取为`FileField`，这是aiohttp中的一个类型。

请注意：尽管通过`view._request`可以获取到原始请求，但并不能保证以aiohttp的方式可以获取到文件！因此应该避免使用`view._request.multipart()`

示例代码：

```python
from slim import Application, ALL_PERMISSION
from slim.base.view import BaseView
from slim.retcode import RETCODE
from aiohttp.web_request import FileField

app = Application(cookies_secret=b'123456', permission=ALL_PERMISSION)


@app.route('test')
class TestView(BaseView):
    @app.route.interface('POST')
    async def upload(self):
        post = await self.post_data()
        field: FileField = post.get('file')
        print(field.file.read())
        self.finish(RETCODE.SUCCESS)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=6666)
```

运行后使用以下命令提交测试请求：

```shell script
curl 'http://127.0.0.1:6666/api/test/upload' -H 'Content-Type: multipart/form-data; boundary=----boundary-test' --data-binary $'------boundary-test\r\nContent-Disposition: form-data; name="file"; filename="slim.txt"\r\nContent-Type: text/plain\r\n\r\nHELLO WORLD\r\n------boundary-test--\r\n' --compressed --insecure
```

服务端打印出文本：
```shell script
[INFO] POST /api/test/upload -> __main__.TestView.upload 200
b'HELLO WORLD'
```
