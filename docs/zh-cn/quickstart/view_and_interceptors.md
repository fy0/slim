# 视图和拦截器

视图(View)是接受Web请求的入口。

我们在视图上绑定接口(Interface)，在接口中处理客户端提交的提交。

## 基础视图 BaseView

[源码地址](https://github.com/fy0/slim/blob/master/slim/base/_view/base_view.py)

### 地址路由

我们以 slim cli 生成的项目为例，其中的 api.index 文件就是一个 BaseView

```python
from slim.base.view import BaseView
from slim.retcode import RETCODE

from app import app


@app.route('misc')
class MiscView(BaseView):
    @app.route.interface('GET')
    async def info(self):
        """
        提供给前端使用的后端配置信息
        """
        self.finish(RETCODE.SUCCESS, {
            'retcode': RETCODE.to_dict(),
            'retinfo': RETCODE.txt_cn,
        })

    @app.route.interface('POST')
    async def hello(self):
        data = await self.post_data()
        self.finish(RETCODE.SUCCESS, 'Hi, %s' % data.get('name', 'visitor'))

```

根据自动生成的接口文档可以知道，这里面定义了一个GET接口，一个POST接口，分别是：
```
GET /api/misc/info
POST /api/misc/hello
```

结合代码，能够看出URL的拼装规律，首先 `/api` 是恒定前缀（可以在app.py中统一修改，Application对象构造函数的mountpoint参数）。

其次 `@app.route('misc')` 提供了第二段地址，函数名 `info` 提供了第三段地址。

`@app.route.interface('GET')`则是将这个方法注册成为了 `GET` 接口。

我们看一下 `app.route.interface` 这个函数的定义：

```python
@staticmethod
def interface(method, url=None, *, summary=None, va_query=None, va_post=None, deprecated=False):
    pass
```

`method` 很好理解，url一般会自动填充为函数名，也可以自定义。

`summary` 是对应生成出接口文档的summary

`va_query` 与 `va_post` 是 [Schematics](https://schematics.readthedocs.io/en/latest/index.html) Model，用于输入校验，分别对应 Query parameter 和 Post body，我们稍后在“表单验证”一节详述。

`deprecated` 用于标记接口是否弃用，标记后会在接口文档上有直接体现。

### Query parameter、Post body 以及其他

作为一个 Web 框架，接口用于处理请求，是其核心。

接口有两个限制：

* 必须定义为某一视图的 async 方法

* 必须调用一次 `self.finish` 来确定返回内容，注意参数code，原则是成功为0，失败为非零。框架提供一组常用返回代码，为 `slim.retcode.RETCODE`，其中异常基本是小于0的，因此开发者自定义异常码最好设计为大于0

`BaseView.finish` 函数定义如下：

```python
def finish(self, code: int, data=sentinel, msg=sentinel, *, headers=None):
    """
    Set response as {'code': xxx, 'data': xxx}
    :param code: Result code
    :param data: Response data
    :param msg: Message, optional
    :param headers: Response header
    :return:
    """
    pass
```

提取 Web 请求中的常用输入数据请看示例：

```python
@app.route('misc')
class MiscView(BaseView):
    @app.route.interface('POST')
    async def hello(self):
        params = self.params  # 获取 parameters
        data = await self.post_data()  # 获取 post 内容
        client_ip = await self.get_ip()  # 获取 IP
        headers = self.headers  # 获取请求头
        role = self.current_request_role  # 当前请求的权限角色
        self.finish(RETCODE.SUCCESS, 'Hi, %s' % data.get('name', 'visitor'))
```

### 表单验证

刚才在讲注册接口的 app.route.interface 函数时，提到了 `va_query` 与 `va_post` 两个参数。

这两个参数分别用于指定 Query parameter 和 Post body 的校验器，这里我们借助 [Schematics](https://schematics.readthedocs.io/en/latest/index.html) 来进行表单验证。

这里还是拿 slim cli 创建的项目举个例子：

```python
from schematics import Model
from schematics.types import EmailType, StringType

from slim.base.types.doc import ValidatorDoc


class SignupDataModel(Model):
    email = EmailType(min_length=3, max_length=30, required=True, metadata=ValidatorDoc('Email'))
    username = StringType(min_length=2, max_length=30, metadata=ValidatorDoc('Username'))
    password = StringType(required=True, min_length=6, max_length=64, metadata=ValidatorDoc('Password'))
    nickname = StringType(min_length=2, max_length=10, metadata=ValidatorDoc('Nickname'))


@app.route('user')
class UserView(PeeweeView, UserMixin):
    model = User

    @app.route.interface('POST', summary='注册', va_post=SignupDataModel)
    async def signup(self):
        """
        用户注册接口
        User Signup Interface
        """
        vpost: SignupDataModel = self._.validated_post

        u = User.new(vpost.username, vpost.password, email=vpost.email, nickname=vpost.nickname)
        if not u:
            self.finish(RETCODE.FAILED, msg='注册失败！')
        else:
            t: UserToken = await self.setup_user_token(u.id)
            self.finish(RETCODE.SUCCESS, {'id': u.id, 'username': u.username, 'access_token': t.get_token()})
```

这里我们定义了 `SignupDataModel` 并用于 /api/user/signup 接口的`va_post`参数

有校验器时，能执行到函数代码即代表校验已通过，使用 `self._.validated_query` 和 `self._.validated_post` 来获取通过对应的 Model 实例。

我们做个请求试一下：

```shell script
http post http://localhost:9618/api/user/signup email=test -v
POST /api/user/signup HTTP/1.1
Accept: application/json, */*
Accept-Encoding: gzip, deflate
Connection: keep-alive
Content-Length: 17
Content-Type: application/json
Host: localhost:9618
User-Agent: HTTPie/1.0.2

{
    "email": "test"
}

HTTP/1.1 200 OK
Content-Length: 159
Content-Type: application/json; charset=utf-8
Date: Wed, 26 Feb 2020 09:41:12 GMT
Server: Python/3.6 aiohttp/3.6.2

{
    "code": -218,
    "data": {
        "email": [
            "Not a well-formed email address."
        ],
        "password": [
            "This field is required."
        ]
    },
    "msg": "非法提交内容"
}
```

请注意这一行代码，这是比直接从 self.post_data() 取值更优的方式： 
```python
vpost: SignupDataModel = self._.validated_post
```

举例来说

```python
class SigninDataModel(Model):
    email = EmailType(min_length=3, max_length=30)
    username = StringType(min_length=2, max_length=30)
    password = StringType(required=True, min_length=6, max_length=64)
    remember = BooleanType(default=True)
```

这里的 remember 参数在 post data 中的形态可能会是 '1' '0' 'true' 'false' 'True' 'False' 等等。

使用 `self._.validated_post.remember` 则可以直接取得 bool 类型的值，非常方便。 

验证器建议放在 api/validate 目录下。

对于 schematics，更详细的用法可以参考其官方文档：

> https://schematics.readthedocs.io/en/latest/basics/quickstart.html


## SQL视图 AbstractSQLView

[源码地址](https://github.com/fy0/slim/blob/master/slim/base/_view/abstract_sql_view.py)

这种视图来自于这样的设想：

> 开发者建立数据表，框架自动生成增删改查API

实际我们是见不到 AbstractSQLView 这个类的，我们会见到的是其子类 `PeeweeView`，能够以这样的形式将 peewee 的 Model 映射出增删改查系列API接口：

```python
@app.route('/topic')
class TopicView(PeeweeView):
    model = Topic
```

得到以下接口：
```
[GET]/api/topic/get
[GET]/api/topic/list/{page}
[GET]/api/topic/list/{page}/{size}
[POST]/api/topic/set
[POST]/api/topic/new
[POST]/api/topic/delete
```

这些接口怎么用我们下一节再统一说，这里先讲一下`AbstractSQLView`的特殊之处。

看下定义：

```python
class AbstractSQLView(BaseView):
    LIST_PAGE_SIZE = 20  # list 单次取出的默认大小，若为-1取出所有
    LIST_PAGE_SIZE_CLIENT_LIMIT = None  # None 为与LIST_PAGE_SIZE相同，-1 为无限
    LIST_ACCEPT_SIZE_FROM_CLIENT = False  # 是否允许客户端指定 page size

    options_cls = SQLViewOptions
    _sql_cls = AbstractSQLFunctions
    is_base_class = True  # skip cls_init check

    table_name: str = None
    primary_key: str = None
    data_model: Type[schematics.Model] = None

    foreign_keys: Dict[str, List[SQLForeignKey]] = {}
    foreign_keys_table_alias: Dict[str, str] = {}  # to hide real table name
```

我们主要关心头三项，用于调整分页大小，跟两个list接口相关。

用法示例：

```python
@app.route('/topic')
class TopicView(PeeweeView):
    model = Topic
    LIST_PAGE_SIZE = 50
```

自动生成的几个接口除了`list`和`bulk_insert`之外，默认情况下都只作用于单条数据。

`set` 和 `delete` 接口在 headers 中增加 bulk 参数，可以影响多条数据。

当 bulk 存在，例如为'true'的时候，接口会对可查询到的全部项起效。bulk还可以是大于零的整数，代表影响的数据项个数。

因为同一类行为的操作既有单条也有多条，因此针对行为，而不是接口设定了以下拦截器：

```python
async def before_query(self, info: SQLQueryInfo):
    """
    在发生查询时触发。
    触发接口：get list set delete
    :param info:
    :return:
    """
    pass

async def after_read(self, records: List[DataRecord]):
    """
    触发接口：get list new set
    :param records:
    :return:
    """
    pass

async def before_insert(self, values_lst: List[SQLValuesToWrite]):
    """
    插入操作之前
    触发接口：new
    :param values_lst:
    :return:
    """
    pass

async def after_insert(self, values_lst: List[SQLValuesToWrite], records: List[DataRecord]):
    """
    插入操作之后
    触发接口：new
    :param values_lst:
    :param records:
    :return:
    """
    pass

async def before_update(self, values: SQLValuesToWrite, records: List[DataRecord]):
    """
    触发接口：set
    :param values:
    :param records:
    :return:
    """
    pass

async def after_update(self, values: SQLValuesToWrite, old_records: List[DataRecord],
                       new_records: List[DataRecord]):
    """
    触发接口：set
    :param values:
    :param old_records:
    :param new_records:
    :return:
    """

async def before_delete(self, records: List[DataRecord]):
    """
    触发接口：delete
    :param records:
    :return:
    """
    pass

async def after_delete(self, deleted_records: List[DataRecord]):
    """
    触发接口：delete
    :param deleted_records:
    :return:
    """
    pass
```

不过，写起来仍然有些别扭，这是我目前能想到的最不差的API设计。

如果有更好的方案，请告诉我。
