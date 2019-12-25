
# 启程

## 安装

首先，使用 pip 安装 slim

```bash
sudo pip3 install slim
```


## 简单示例

这是一个简单的 peewee 使用 sqlite 为后端并创建数据表的例子

model.py

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

现在直接运行 python main.py 会显示如下：

```shell
app.permission is ALL_PERMISSION, it means everyone has all permissions for any table
This option should only be used in development environment
======== Running on http://0.0.0.0:9999 ========
```
说明：slim cli工具自动生成的配置文件是随机的以9开头的四位端口号，格式为 9%03d

使用浏览器打开 http://localhost:9999/api/aiohttp_request 或 localhost:9999/api/aiohttp_request 即可看到

```html
hello
```

使用浏览器打开 http://localhost:9999/api/example/get 即可看到

```json
{
	"code": -249,
	"data": "Nothing found from table 'example'",
	"msg": "未找到"
}
```

因为还数据库example表中没有找到对应的数据

使用浏览器打开 http://localhost:9999/api/example/list/1 即可看到

```json
{
	"code": 0,
	"data": {
		"cur_page": 1,
		"prev_page": null,
		"next_page": 2,
		"first_page": null,
		"last_page": null,
		"page_numbers": [],
		"info": {
			"page_size": 20,
			"page_count": 0,
			"items_count": 0
		},
		"items": []
	}
}
```

使用浏览器向 http://0.0.0.0:9999/api/misc/hello POST数据即可看到

```json
{
	"code": 0,
	"data": "Hi, visitor"
}
```

使用浏览器打开 http://0.0.0.0:9999/api/misc/info 即可看到获取综合信息

```json
{
	"code": 0,
	"data": {
		"retcode": {
			"FAILED": -255,
			"TIMEOUT": -254,
			"UNKNOWN": -253,
			"TOO_FREQUENT": -252,
			"DEPRECATED": -251,
			"NOT_FOUND": -249,
			"ALREADY_EXISTS": -248,
			"PERMISSION_DENIED": -239,
			"INVALID_ROLE": -238,
			"CHECK_FAILURE": -229,
			"PARAM_REQUIRED": -228,
			"POSTDATA_REQUIRED": -227,
			"INVALID_PARAMS": -219,
			"INVALID_POSTDATA": -218,
			"SUCCESS": 0,
			"WS_DONE": 1
		},
		"retinfo": {
			"0": "成功",
			"-255": "失败",
			"-254": "超时",
			"-253": "未知错误",
			"-252": "请求过于频繁",
			"-251": "此接口已不推荐使用",
			"-249": "未找到",
			"-248": "已存在",
			"-239": "无权访问",
			"-238": "无效的权限角色",
			"-229": "校验失败",
			"-228": "缺少参数",
			"-227": "缺少提交内容",
			"-219": "非法参数",
			"-218": "非法提交内容",
			"1": "Websocket 请求完成"
		}
	}
}
```

所有接口请参考“简单示例”和“标准预设接口”
