# 查询和修改

## 简单查询

回忆一下“启程”一节的 Helloworld：

```python
from peewee import *
from slim.ext.view.support import PeeweeView

class Topic(Model):
    title = CharField(index=True, max_length=255)
    time = BigIntegerField(index=True)  # 时间戳
    content = TextField()

    class Meta:
        database = db

# ...

@app.route.view('topic')
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
[POST]/api/topic/bulk_insert
[POST]/api/topic/delete
```

预设接口覆盖了常见的增删改查操作。

对于这些API，我们有两个简单的基本原则：

* 使用查询参数（通常叫做query string 或 parameters）来选择数据。
* 使用POST数据，来代表添加或修改。

举例来说，当我们想获得 id 为 1 的 Topic，进行以下请求：

```shell script
http http://localhost:9999/api/topic/get?id=1
```

返回结果如下：
```json
{
    "code": 0,
    "data": {
        "content": "World",
        "id": 1,
        "time": 1582862999,
        "title": "Hello"
    }
}
```

获得标题为 hello 的 Topic，进行以下请求：

```shell script
http http://localhost:9999/api/topic/get?title=hello
```

获得 id 为 1 且标题为 hello 的 Topic：

```shell script
http http://localhost:9999/api/topic/get?id=1&title=hello
```

获得创建时间晚于2020年1月1日的所有文章，并以时间降序排序：

```shell script
http http://localhost:9999/api/topic/list/1?time.ge=1577808000&order=time.desc
```

```json
{
    "code": 0,
    "data": {
        "cur_page": 1,
        "first_page": null,
        "info": {
            "items_count": 4,
            "page_count": 1,
            "page_size": 20
        },
        "items": [
            {
                "content": "World",
                "id": 4,
                "time": 1582870631,
                "title": "Hello4"
            },
            {
                "content": "World",
                "id": 3,
                "time": 1582870629,
                "title": "Hello3"
            },
            {
                "content": "World",
                "id": 2,
                "time": 1582870628,
                "title": "Hello2"
            },
            {
                "content": "World",
                "id": 1,
                "time": 1582870627,
                "title": "Hello"
            }
        ],
        "last_page": null,
        "next_page": null,
        "page_numbers": [
            1
        ],
        "prev_page": null
    }
}
```

请注意：

**除了 new 之外的所有API，都需要用Query string选择数据，他们都遵从相同的规则。**

此外，所有查询条件是and关系。这会造成一些限制，但在绝大多数情况下够用而且不会引发性能和安全问题。


## 选择查询列

在查询时，可能并非所有列都是需要的。我们可以通过在请求参数中添加select字段来选择希望存在的列，格式为：

```
?select=column1, column2
```

逗号后面的空格可以省略。

例如，我们希望显示文章标题列表，此时直接使用 list 接口会连同文章内容一起得到，我们可以这样：

```shell script
http "http://localhost:9999/api/topic/list/1?time.ge=1577808000&order=time.desc&select=id,title"
```

```json
{
    "code": 0,
    "data": {
        "cur_page": 1,
        "first_page": null,
        "info": {
            "items_count": 4,
            "page_count": 1,
            "page_size": 20
        },
        "items": [
            {
                "id": 4,
                "title": "Hello4"
            },
            {
                "id": 3,
                "title": "Hello3"
            },
            {
                "id": 2,
                "title": "Hello2"
            },
            {
                "id": 1,
                "title": "Hello"
            }
        ],
        "last_page": null,
        "next_page": null,
        "page_numbers": [
            1
        ],
        "prev_page": null
    }
}
```


## 接口权限

你肯定已经想到，对全部用户直接暴露所有的接口和数据是不合适的。

关于这点，有三个解决方案：

一、关闭接口

```python
@app.route.view('user')
class UserViewView(PeeweeView, UserViewMixin):
    model = User

    @classmethod
    def interface(cls):
        super().interface()
        cls.discard('new')
        cls.discard('delete')
```

二、设定权限

```
待编写
```

三、设定准入角色

```
待编写 使用装饰器
```

## 查询运算符

回顾一下这个请求：

```shell script
http http://localhost:9999/api/topic/get?time.ge=1577808000
```

这里使用了一个运算符，`time.ge`，即大于等于(GreaterEqual)。

看到这个熟悉的算符，那么你肯定已经想到，其他的算符(比如 gt le lt eq等等)是否也支持呢？

当然，支持的运算符包括以下这些：

```
比较：
    相等 eq
    不等 ne
    小于 lt
    小于等于 le
    大于等于 ge
    大于gt

包含：
    包含 in [后接json数组]
    不包含 notin [后接json数组]
    存在于 contains  # 用于array field，检查后接的值是否在array中

全等：
    全等于 is [只能接null]
    不全等于 isnot [只能接null]

其他：
    模糊匹配 like
    不区分大小写模糊匹配(PostgreSQL) ilike
```


## 返回值

无论什么请求，只要没有抛出异常，那么都返回状态码200并附带一段json数据。

其形式统一为：{'code': num, 'data': data}

即一个数字代码(即code)，和附加数据(data)

返回值为 0 代表成功，非零代表失败

**返回值代码列表**
```python
# module: slim.retcode

class RETCODE(StateObject):
    SUCCESS = 0  # 成功
    FAILED = -255  # 失败
    TIMEOUT = -254  # 超时
    UNKNOWN = -253  # 未知错误
    TOO_FREQUENT = -252  # 请求过于频繁
    DEPRECATED = -251  # 已废弃

    NOT_FOUND = -249  # 未找到
    ALREADY_EXISTS = -248  # 已存在

    PERMISSION_DENIED = -239  # 无权访问
    INVALID_ROLE = -238  # 权限申请失败

    CHECK_FAILURE = -229  # 校验失败（文件上传等）
    PARAM_REQUIRED = -228  # 需要参数
    POSTDATA_REQUIRED = -227  # 需要参数

    INVALID_PARAMS = -219  # 非法参数
    INVALID_POSTDATA = -218  # 非法提交内容

    WS_DONE = 1  # Websocket 请求完成
```
 
对于预设接口，当返回值为0时，get接口会在data中得到query string所指向的那一条数据。
 
当returning不开启，delete、set、new会返回data为1或0，代表影响的数据条目数。
 
当returning开启时，delete、set也会得到相同的内容，而new则返回刚才创建出的记录。

而list接口则以分页形式返回多条数据记录，具体数据格式建议查看自动生成的文档，更为直观。

## 修改/新建

与使用query string代表查询相对应，我们使用post body来代表对数据记录的修改/新建。

```json
{
    "title": "Hello Again",
    "content": "Content changed"
}
```

修改文章内容：

```shell script
http -f POST "http://localhost:9999/api/topic/set?id=1" title="Hello Again" content="Content changed"
```

返回结果

```json
{
    "code": 0,
    "data": 1
}
```

新建一篇文章：

```shell script
http -f POST "http://localhost:9999/api/topic/new" title="Hello Again" content="Content changed" time=1578729600 returning=true
```

返回结果

```json
{
    "code": 0,
    "data": {
        "content": "Content changed",
        "id": 78,
        "time": 1578729600,
        "title": "Hello Again"
    }
}
```

## 与拦截器结合使用

上一小节中我们通过向`new`接口发送请求，新建了一条记录。

但这个请求需要我们每次手写 time 参数，十分不便。关于这点，有两种解决方案：

其一，修改数据表的声明，添加default的内容。这对时间来说足矣。

```python
import time

class Topic(Model):
    title = CharField(index=True, max_length=255)
    time = BigIntegerField(index=True, default=time.time)  # 时间戳
    content = TextField()

    class Meta:
        database = db
```

其二，使用拦截器 `before_insert`

```python
import time

@app.route.view('topic')
class TopicView(PeeweeView):
    model = Topic

    async def before_insert(cls, values_lst: List[SQLValuesToWrite]):
        for values in values_lst:
            values['time'] = int(time.time())
```

## 特殊参数

在headers中有两个特殊参数。

1. returning

    存在此项时，各默认api会尽量返回内容替代影响数字。

2. bulk

    当 bulk 存在，例如为'true'的时候，接口会对可查询到的全部项起效。bulk还可以是大于零的整数，代表影响的数据项个数。
