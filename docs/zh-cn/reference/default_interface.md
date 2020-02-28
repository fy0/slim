
# 标准预设接口


## [GET] 单条数据获取接口

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


## [LIST] 列表数据获取接口
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


## [SET] 单条数据赋值接口
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

## [NEW] 数据创建接口
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

## [DEL] 单条数据删除接口
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
