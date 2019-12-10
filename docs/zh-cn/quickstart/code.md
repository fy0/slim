## 源码简介
以下0.4.11为例代码结构如下：
```
├─tools
│  ├─request.py # 定义SlimViewRequest，可用于测试或后端接口
│  └─__init__.py # 无代码
├─ext
│  ├─decorator.py #定义require_role、must_be_role、get_cooldown_decorator三个装饰器，主要用于权限设置、接口冷却
│  └─__init__.py # 无代码
├─utils # 各种辅助工具
│  ├─state_obj.py # 类似 Enum
│  ├─cls_init.py # 提供元类 MetaClassForInit，据此创建的类型会自动调用 cls_init 函数
│  ├─binhex.py #用于从数据库获取到 bytes,二进行制和十六进制互转换
│  ├─myobjectid.py # 12位分布式ID生成器
│  ├─pagination.py # 分页工具，已应用于框架本身
│  ├─async_run.py # async_run用于初始化数据库连接
│  ├─count_dict.py # 计数字典
│  ├─proxy.py
│  ├─jsdict.py # 计数字典
│  ├─autoload.py # 用于自动导入某一目录下的所有 python 模块
│  ├─json_ex.py # json.dumps的扩展函数，支持memoryview、bytes、set、DataRecord，已应用于框架本身及lcarus
│  ├─customid.py # 12位分布式ID生成器
│  ├─__init__.py # 提供BoolParser、BlobParser、JSONParser用于ORM
│  └─umsgpack.py
├─base # 框架核心代码
│  ├─app.py
│  ├─ws.py
│  ├─route.py
│  ├─sqlfuncs.py
│  ├─log.py
│  ├─__init__.py
│  ├─view.py
│  ├─user.py
│  ├─sqlquery.py
│  ├─session.py
│  ├─permission.py
│  └─helper.py
├─support # 框架数据库驱动
│  ├─peewee # peewee驱动
│  │  ├─__init__.py
│  │  └─view.py # 实现PeeweeDataRecord、PeeweeContext、PeeweeSQLFunctions、PeeweeViewOptions、PeeweeView类和field_class_to_sql_type函数
│  ├─asyncpg # PostgreSQL驱动，通过asyncpg
│  │  ├─__init__.py 
│  │  ├─view.py # 实现AsyncpgDataRecord、AsyncpgSQLFunctions、AsyncpgViewOptions、AsyncpgView类，引入query模块内各个*Compiler类
│  │  └─query.py # 实现Column、BaseCompiler、SelectCompiler、UpdateCompiler、InsertCompiler类
│  └─__init__.py # 无代码
├─exception.py #定义框架各种异常
├─__init__.py #引入各个模块，定义版本号
└─retcode.py # 定义返回值
```