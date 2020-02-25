# 启程

## 介绍

这份文档会展示 slim 在开发中用到的大多数功能。

我本来写了一些东西来阐述 slim 的设计思路，不过还是觉得没有必要特意去讲，因为实际的代码会更加直观。这也是所谓一图胜千言吧。

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
from slim import Application, CORSOptions, ALL_PERMISSION, NO_PERMISSION
from slim.support.peewee import PeeweeView


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


@app.route('/topic')
class TopicView(PeeweeView):
    model = Topic


app.run(host='0.0.0.0', port=9999)
```

使用命令运行

```shell
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
[POST]/api/topic/delete
```

同时，访问此地址可以看到API文档：
```
http://localhost:9999/redoc
```


## 使用 cli 工具快速开始

建议使用这种方式来创建项目，来得到结构简明的初始项目。

使用如下命令：

```bash
slim init
```

来创建项目，在随后填入项目名

```
> slim init
Project Name: MyProject
Start a web application.
OK!
```
