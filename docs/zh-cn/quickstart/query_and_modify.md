# 查询和修改

## 简单查询

回忆一下“启程”一节的 Helloworld：

```python
from peewee import *
from slim.support.peewee import PeeweeView

class Topic(Model):
    title = CharField(index=True, max_length=255)
    time = BigIntegerField(index=True)  # 时间戳
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

预设接口覆盖了常见的增删改查操作。

对于这些API，我们有两个简单的基本原则：

* 使用查询参数（通常叫做query string 或 parameters）来选择数据。
* 使用POST数据，来代表添加或修改。

举例来说，当我们想获得 id 为 1 的 Topic，进行以下请求：

```shell script
http http://localhost:9999/topic/get?id=1
```

返回结果如下：
```
...
```

获得标题为 hello 的 Topic，进行以下请求：

```shell script
http http://localhost:9999/topic/get?title=hello
```

获得 id 为 1 且标题为 hello 的 Topic：

```shell script
http http://localhost:9999/topic/get?id=1&title=hello
```

获得创建时间晚于2020年1月1日的所有文章：

```shell script
http http://localhost:9999/topic/get?time.ge=1577808000
```

获得创建时间晚于2020年1月1日的所有文章，并以时间降序排序：

```shell script
http http://localhost:9999/topic/get?time.ge=1577808000&order=time.desc
```

请注意：
**需要用Query string选择数据的API是除了new之外的所有API，他们都遵从相同的规则。**

此外，所有查询条件是and关系。这诚然会造成一些现实，但在绝大多数情况下够用而且不会引发性能和安全问题。

## 接口权限

你肯定已经想到，对全部用户直接暴露所有的接口和数据是不合适的。

关于这点，有三个解决方案：

一、关闭接口

二、设定权限

三、设定准入角色


## 查询运算符

回顾一下这个请求：

```shell script
http http://localhost:9999/topic/get?time.ge=1577808000
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

