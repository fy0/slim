
# 基础设计

## 概述
---

如前文所说，slim 默认会将数据表封装为一套web接口，而这些接口遵循一些共同原则。

除了默认的接口之外，可以自行扩展新的接口，也可以重载或者关闭默认接口。

一般来说，我们利用 HTTP 请求附带的参数（params）来进行数据的查询和选择，等价于使用and连接的sql条件语句，同时支持部分运算符。

利用 HTTP POST 请求中可以附加的 body 信息来表示数据被添加或更新的内容。

因此值得注意的是，部分请求可能需要同时带上这两套参数，比如说 set（提交POST请求，使用 params 选择数据，使用 post data 描述数据内容）。

根据开发者在绑定url到服务实例对象上时给出的名字，这一套API会被自动带上如下的前缀：

```
/api/{name}/{method}
```

{method} 用来代表预设接口，一共六个：
```
get
list
set
new
delete
```

预设接口覆盖了常见的增删改查操作。


## 返回值
---

所有接口返回值统一为 {'code': num, 'data': data} 的形式

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


## 可用查询运算符
---

['=', '==', '!=', '<>', '<', '<=', '>', '>=', 'eq', 'ne', 'ge', 'gt', 'le', 'lt', 'in', 'is', 'isnot']

is 和 isnot 还未彻底完成，但注意，这两个的值都只有 null 一个，其他值都会报错。


## 标准预设接口
---

一般来说单个接口和单个数据库表是一对一的关系，因此如无特别说明，即存在若干默认接口：

### [GET] 单条数据获取接口

```
/api/{name}/get
```

    请求方式：
        get

    params：
        key 为列名与算符的组合，例如id name age等，带算符的话例如 age.lt，意为 “age 小于”
        value 为匹配值
        特别的，名为 order 的 key 是一个保留字，因此不要给列起这样的名字。
        order 可以使用这样的语法：order=id.desc,name.asc

    示例：
        取出 id 为 1 的项
        http://localhost:9999/api/xxx/get?id=1

        取出名字为 "张三" 且年龄小于21的项
        http://localhost:9999/api/xxx/get?name=张三&age.lt=21

返回结果
```json
{
    "code": 0,
    "data": {
        "id": 1,
        "name": "张三",
        "age": 20,
    }
}
```


### [LIST] 列表数据获取接口
```
/api/{name}/list/{page}
/api/{name}/list/{page}/{size}
```

    说明：
        自带分页信息的列表形式数据获取接口
        必须经过服务端允许，才能让 size 参数生效（否则用户可以使用一条命令抓取整个数据库）

    请求方式：
        get

    params：
        key 为列名与算符的组合，例如id name age等，带算符的话例如 age.lt，意为 “age 小于”
        value 为匹配值
        规则与 get 完全一致

    示例：
        列出第一页的所有项
        http://localhost:9999/api/xxx/list/1

        列出 id 大于 10 的项
        http://localhost:9999/api/xxx/list/1?id.gt=10

返回结果
```json
{
    "code": 0,
    "data": {
        "cur_page": 1,
        "prev_page": null,
        "next_page": 2,
        "first_page": null,
        "last_page": null,
        "page_numbers": [
            1,
            2
        ],
        "info": {
            "page_size": 20,
            "page_count": 2,
            "items_count": 35
        },
        "items": [
            {
                "id": 1,
                "name": "张三",
                "age": 20
            },
            {
                "id": 2,
                "name": "李四",
                "age": 23
            },
            ...
        ]
    }
}
```


### [SET] 单条数据赋值接口
```
/api/{name}/set
```

    说明：
        这个接口会将 params 查出来的在数据表中的条目，用 body 给出的值进行 update 操作

    请求方式：
        post

    params：
        key 为列名与算符的组合，例如id name age等，带算符的话例如 age.lt，意为 “age 小于”
        value 为匹配值
        规则与 get 完全一致

    body(post data)：
        key 为列名，value 为值

    示例：
        将 id 为 1 的项名字设为张三
        http://localhost:9999/api/xxx/set?id=1
        {name: '张三'}

返回结果
```json
{
    "code": 0,
    "data": {
        "count": 1
    }
}
```

### [NEW] 数据创建接口
```
/api/xxx/new
```

    说明：
        这个接口用 body 给出的值进行 insert 操作

    请求方式：
        post

    params：
        无

    body(post data)：
        key 为列名，value 为值

    示例：
        插入一条数据
        http://localhost:9999/api/xxx/new
        {name: '张三', age: 20}

返回结果
```json
{
    "code": 0,
    "data": {
        "id": 1,
        "name": "张三",
        "age": 20
    }
}
```

### [DEL] 单条数据删除接口
```
/api/{name}/delete
```

    说明：
        这个接口用来删除一条数据

    请求方式：
        post

    params：
        key 为列名与算符的组合，例如id name age等，带算符的话例如 age.lt，意为 “age 小于”
        value 为匹配值
        规则与 get 完全一致

    示例：
        删除一条数据
        http://localhost:9999/api/xxx/delete?id=1


返回结果
```json
{
    "code": 0,
    "data": {}
}
```

## 选择查询列
---
你可以通过select来实现该功能，前端后端均可。

### 前端示例
1. 如Icarus前端通过select: ['id', 'title', 'ref']对后端请求查询。
注：以下代码示例在 Icarus/src/views/wiki/history.vue ，

```javascript
let getArticle = async () => {
    let ret = await this.$api.wiki.get({
        id: params.id,
        select: ['id', 'title', 'ref']
    }, this.basicRole)
    if (ret.code === this.$api.retcode.SUCCESS) {
        this.article = ret.data
    } else if (ret.code === this.$api.retcode.NOT_FOUND) {
        this.notFound = true
    } else {
        wrong = ret
    }
}

```
2. 前端请求经carus/src/netapi.js文件中的 SlimViewRequest 类传给slim框架，get函数如下：

```javascript
async get (params, role = null) {
    if (params && params.loadfk) {
        params.loadfk = JSON.stringify(params.loadfk)
    }
    return nget(`${this.urlPrefix}/get`, params, role)
}
```

3. 查询传给slim框架后，slim执行 AbstractSQLView类的 get 函数 ，get函数通过调用 slim/base/sqlquery.py 文件中 SQLQueryInfo 类中的 parse 函数取出select所传递的字段名，并调用 AbstractSQLFunctions 类的 select_one 函数查询数据库表和 AbstractSQLView 类的 load_fk 函数查询外键完成数据查询。
注：select_one 函数在数据库驱动中分别实现

### 后端示例

也可在你的后端代码中执行select查询，ORM帮我们完成这一切。

如Icarus后端通过Topic.select(Topic.id)、WikiArticle.select(WikiArticle.id)或Comment.select(Comment.id)完成查询。

注：以下代码示例在 Icarus/backend/model/esdb.py

```python
def update_all(reset=False):
    if reset:
        try:
            es.indices.delete(index=INDEX_NAME)
        except elasticsearch.exceptions.NotFoundError:
            pass
        create_index()

    for i in Topic.select(Topic.id):
        print('topic', to_hex(i.id))
        es_update_topic(i.id)

    for i in WikiArticle.select(WikiArticle.id):
        print('wiki', to_hex(i.id))
        es_update_wiki(i.id)

    for i in Comment.select(Comment.id):
        print('comment', to_hex(i.id))
        es_update_comment(i.id)
```

## 跨表查询
---
当然如果你直接使用peewee等ORM来实现查询功能是没有问题，下面以lcarus为例来说明slim推荐做法：

1、定义Model
以下代码示例在Icarus/backend/model/manage_log.py 
```python
class ManageLog(BaseModel):
    id = BlobField(primary_key=True)  # 使用长ID
    user_id = BlobField(index=True, null=True)  # 操作用户
    role = TextField(null=True)  # 操作身份
    time = MyTimestampField(index=True)  # 操作时间
    related_type = IntegerField()  # 被操作对象类型
    related_id = BlobField(index=True)  # 被操作对象
    related_user_id = BlobField(index=True, null=True)  # 被操作对象涉及用户
    operation = IntegerField()  # 操作行为
    value = BinaryJSONField(dumps=json_ex_dumps, null=True)  # 操作数据
    note = TextField(null=True, default=None)
```
注：BaseModel继承自peewee.Model

2、继承PeeweeView定义你需要视图，使用add_soft_foreign_key添加外键
以下代码示例在Icarus/backend/view/logs.py 
```python
@route('log/manage')
class LogManageView(PeeweeView):
    model = ManageLog

    @classmethod
    def ready(cls):
        cls.add_soft_foreign_key('user_id', 'user')
```

注：PeeweeView类继承自 AbstractSQLView 类， add_soft_foreign_key 函数在slim/base/view.py中AbstractSQLView定义。

add_soft_foreign_key函数用于存储外键，但这不是一个外键（这样处理是为了避免“外键约束”）。

如果add_soft_foreign_key函数中的数据库表不存在，则slim会在执行loadfk时报错

3、进行查询
以下代码示例在Icarus/src/views/wiki/history.vue

```javascript
let getHistory = async () => {
    console.log(1111, this.$api.logManage, this.$api.user)
    let ret = await this.$api.logManage.list({
        related_id: params.id,
        order: 'time.desc',
        loadfk: { 'user_id': null }
    }, pageNumber, null, this.basicRole)
    if (ret.code === this.$api.retcode.SUCCESS) {
        this.page = ret.data
    } else if (ret.code === this.$api.retcode.NOT_FOUND) {
        this.page.items = []
    } else {
        wrong = ret
    }
}
```
注：如果想了解前后端的交互过程可以参考以下代码：
 前端部分：Icarus/src/netapi.js 中的 class SlimViewRequest，里面定义了get/list/set/update/new/delete接口
 前端部分的set/update均对应后端中的update接口
 