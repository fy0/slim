# 启程

## 介绍

这份文档会展示 slim 在开发中用到的大多数功能。

我本来写了一些东西来阐述 slim 的设计思路，不过还是觉得没有必要特意去讲，因为实际的代码会更加直观。

我们将会创建一个简单的 Web 后端程序，包含若干个API，用于对一个数据表进行增删改查操作。


## 安装

首先，使用 pip 安装 slim

```bash
pip3 install slim
```

## 极简示例

```bash
pip3 install slim peewee
```


```python
from peewee import *
from playhouse.db_url import connect
from slim import Application, CORSOptions, ALL_PERMISSION, EMPTY_PERMISSION
from slim.ext.view.support import PeeweeView


db = connect("sqlite:///database.db")


class Topic(Model):
    title = CharField(index=True, max_length=255)
    time = BigIntegerField(index=True)
    content = TextField()

    class Meta:
        database = db

db.connect()
db.create_tables([Topic], safe=True)


app = Application(
    cookies_secret=b'cookies secret',
    permission=ALL_PERMISSION,
    cors_options=CORSOptions('*', allow_credentials=True, expose_headers="*", allow_headers="*"),
    client_max_size=1000*1024*1024
)


@app.route.view('topic')
class TopicView(PeeweeView):
    model = Topic


app.run(host='0.0.0.0', port=9999)
```

使用命令运行

```shell script
python app.py
======== Running on http://0.0.0.0:9999 ========
(Press CTRL+C to quit)
```

此时有以下接口可用：

```
[GET]/api/topic/get
[GET]/api/topic/list/{page}
[GET]/api/topic/list/{page}/{size}
[POST]/api/topic/set
[POST]/api/topic/new
[POST]/api/topic/bulk_insert
[POST]/api/topic/delete
```

同时，访问此地址可以看到API文档：
> http://localhost:9999/redoc


## 使用 cli 工具快速开始

建议使用这种方式来创建项目，来得到结构简明的初始项目。

使用如下命令来创建项目：

```shell script
slim init
```

随后填入项目名，回车

```shell script
> slim init
Project Name: MyProject
Start a web application.
OK!
```

运行项目：

```shell script
cd MyProject
pip install -r requirements.txt
python main.py

======== Running on http://0.0.0.0:9618 ========
(Press CTRL+C to quit)
```

端口号以9为开头，后三位随机，这次我们得到的是9618，因此访问：

> http://localhost:9618/redoc

> http://localhost:9618/redoc?role=user

就可以看到API文档了。

因为用户角色有visitor和user两种，他们对应的API是不同的，所以文档也分为两个。


我们得到的项目结构：

```
tree -I "__pycache__|__init__.py|database.db"  --dirsfirst

.
├── api  # 存放 api接口
│   ├── validate  # 存放验证器
│   │   └── user.py  # UserView 的验证器
│   ├── _views.py
│   ├── example.py
│   ├── index.py
│   └── user.py
├── model  # 借助 ORM 构造的 Model 层
│   ├── _models.py
│   ├── example.py
│   ├── test.py
│   ├── user.py
│   └── user_token.py
├── permissions  # 角色权限描述
│   ├── roles  # 角色定义，可视为RBAC
│   │   ├── user.py
│   │   └── visitor.py
│   ├── tables  # 数据权限，可视为ACL
│   │   ├── _vars.py
│   │   └── user.py
│   ├── role_define.py  # 角色名称定义
│   └── roles_apply.py  # 引用此文件使机制起效
├── tools  # 辅助工具
│   ├── netapi.js  # 请求封装 - js
│   └── request.py  # 请求封装 - python
├── app.py
├── config.py
├── main.py
└── requirements.txt
```

## 扩展阅读

- [视图和拦截器](quickstart/view_and_interceptors.md)
- [查询和修改](quickstart/query_and_modify.md)
- [注释和文档](quickstart/comment_and_doc.md)
- [用户和权限](quickstart/user_and_permission.md)
