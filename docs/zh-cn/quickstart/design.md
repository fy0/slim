
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


## 跨表查询
---
