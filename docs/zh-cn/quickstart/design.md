
# 基础设计

## 概述
---

如前文所说，slim 会将数据表封装为一套web接口，而这些接口会遵循一些共同原则。

一般来说，我们利用 HTTP 请求附带的参数（params）来进行数据的查询和选择，等价于使用and连接的sql条件语句，同时支持部分运算符。

利用 HTTP POST 请求中可以附加的 body 信息来表示数据被添加或更新的内容。

因此值得注意的是，一些请求可以同时带上这两套参数。

此外，根据开发者在绑定url到服务实例对象上时给出的名字，这一套API会被自动带上如下的前缀：

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

那么如何进行绑定，这些接口又有什么用呢？

请继续往下看。

## 返回值
---

所有接口返回值统一为 {'code': num, 'data': data} 的形式

即一个数字代码(即code)，和附加数据(data)

返回值为 0 代表成功，非零代表失败

**返回值代码列表**
```python
# module: slim.retcode

class RETCODE:
    SUCCESS = 0  # 成功
    TIMEOUT = -244  # 超时
    CHECK_FAILURE = -245  # 校验失败（文件上传等）
    PARAM_REQUIRED = -246  # 需要参数
    FAILED = -247  # 失败
    TOO_LONG = -248  # 过长（用户名或其他参数）
    TOO_SHORT = -249  # 过短（用户名或其他参数）
    INVALID_POSTDATA = -243  # 非法提交内容
    INVALID_PARAMS = -250  # 非法参数
    ALREADY_EXISTS = -251  # 已经存在
    NOT_FOUND = -252  # 未找到
    UNKNOWN = -253  # 未知错误
    NOT_USER = -254  # 未登录
    INVALID_ROLE = -246  # 权限申请失败
    PERMISSION_DENIED = -255  # 无权访问
```


## 可用查询运算符
---

['=', '==', '!=', '<>', '<', '<=', '>', '>=', 'eq', 'ne', 'ge', 'gt', 'le', 'lt', 'in', 'is', 'isnot']

is 和 isnot 还未彻底完成，但注意，这两个的值都只有 null 一个，其他值都会报错。


## 标准预设接口
---

一般来说单个接口和单个数据库表是一对一的关系，因此如无特别说明，即存在若干默认接口：

### 单条数据获取接口

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


### 列表数据获取接口
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
        "page_count": 2,
        "info": {
            "page_size": 20,
            "count_all": 35
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


### 数据赋值接口
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

### 数据创建接口
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

### 单条数据删除接口
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

## 无害化
---

Slim 将遵循以下几个原则，或者说是限制：

* 只面向单表，要使用联合查询建议配合使用 sql 中的 view

* 只允许简单逻辑关系，所有查询参数以 and 连接


Slim 给了前端极大的自由度去访问和编辑数据。

我们先抛开权限管理不谈（这块内容较多，将在后面用专门一节进行详细阐述），已有的内容似乎就已经十分危险。

比如用户可能会滥用 list 接口去想方设法的弄出他感兴趣的数据，在服务端运行的情况下通过设定 size 参数更是有可能一次性抓下整个数据表。

比如我们不希望用户看到表中的一些数据，但当用户拥有高权限（例如他是个管理员）的时候又可以得到更多信息。

再比如更新或删除数据时如果设置错了条件可能会造成极为严重的后果，如果面临 xss 威胁时更是如此。

这些都是我所担心的。我将会提供各种配置项让用户对诸如单次获取的最多项，修改或删除的条目数量进行限制。

而表中向哪些用户在什么情况下暴露哪些数据已经可以通过权限系统进行限制了。

## 其他
---

关于 View.post_data() 与 View.params()

注意，尽量不要直接使用 await View.request.post()
原因是这样的。


举例
```python
async def new(self):
    post_data = await self.request.post()
    post_data['id'] = ObjectID().to_hex()
    super().new()
```

当我们希望重载某些预置方法，对一些参数进行干涉处理的时候

```bash
TypeError: 'multidict._multidict.MultiDictProxy' object does not support item assignment
```

这样的事情就会发生（修改数据的企图被拒绝了）。

而 View.post_data() 与 View.params() 会使用缓存字典来存放数据。

因此你可以在它们被使用前修改它们以影响默认行为。

