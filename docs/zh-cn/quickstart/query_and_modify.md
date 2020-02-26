# 查询和修改



回忆一下“启程”一节的 Helloworld：

```python
from peewee import *
from slim.support.peewee import PeeweeView

class Topic(Model):
    title = CharField(index=True, max_length=255)
    time = BigIntegerField(index=True)
    content = TextField()

    class Meta:
        database = db

# ...

@app.route('/topic')
class TopicView(PeeweeView):
    model = Topic
```

最后三行代码对应以下API：

```
[GET]/api/topic/get
[GET]/api/topic/list/{page}
[GET]/api/topic/list/{page}/{size}
[POST]/api/topic/set
[POST]/api/topic/new
[POST]/api/topic/delete
```

对于这些API，我们有两个简单的基本原则：

* 使用查询参数（通常叫做query string 或 parameters）来选择数据。
* 使用POST数据，来代表添加或修改。

举例来说，当我们想获得 id 为 1 的 Topic，进行以下请求：

```shell script
http http://localhost:9999/topic/get?id=1
```

获得标题为 hello 的 Topic，进行以下请求：

```shell script
http http://localhost:9999/topic/get?title=hello
```

获得 id 为 1 且标题为 hello 的 Topic

