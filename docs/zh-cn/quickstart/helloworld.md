
# 启程

## 简单示例

model.py 这是一个简单的 peewee 使用 sqlite 为后端并创建数据表的例子

```python

from peewee import *
from playhouse.db_url import connect

db = connect("sqlite:///database.db")

class Topic(Model):
    title = CharField(index=True, max_length=255)
    time = BigIntegerField(index=True)
    content = TextField()

    class Meta:
        database = db

db.connect()
db.create_tables([Topic], safe=True)
```

app.py 加载 model 并绑定到 9999 端口
```python
from slim import app_init
from slim.support.peewee import PeeweeView
from slim.base.helper import Route
from aiohttp import web

route = Route()

@route('/topic')
class TopicView(PeeweeView):
    model = Topic

app = app_init(b'cookies secret', enable_log=True, route=route)
web.run_app(app, host='0.0.0.0', port=9999)
```

```shell
python app.py
======== Running on http://0.0.0.0:9999 ========
(Press CTRL+C to quit)
```

此时有以下接口可用

```
[GET]/api/topic/get
[GET]/api/topic/list/{page}
[GET]/api/topic/list/{page}/{size}
[POST]/api/topic/set
[POST]/api/topic/new
[POST]/api/topic/delete
```

## 使用 cli 工具快速开始

建议使用这种方式来创建项目，新项目包括：

* 简明的标准化项目结构

* 自动随机生成的 cookies 加密密钥

* 为 peewee 和 asyncpg 分别提供了配置代码

* gitignore 文件

* requirements.txt

* config.py 文件

首先，使用 pip 安装 slim

```bash
sudo pip3 install slim
```

安装完成后可以使用命令：

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

这个过程就完成了。

建议随后在项目目录使用

```bash
pip install -r requirements.txt
```

来安装可能缺少的依赖。

随后在 model 目录下存放数据库访问相关的代码。

在 view 目录的文件下引用 `PeeweeView` 或 `AsyncpgView` 以绑定新的接口。
