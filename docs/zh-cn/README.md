
## 关于

> slim 是一个探索性质 python web 后端框架（底层基于aiohttp），它能够直接将 SQL 数据表直接绑定为 web 接口，并配有一个基于角色与数据表的管理权限模块。


### 特性

* 基于 aiohttp，全异步请求

* 映射数据表的增删改查为 web 接口

* 支持 url 路由装饰器 @route

* 简单的 session 支持

* 基于数据表的权限管理

* 简单命令行工具slim init，可用于初始化项目目录

* 附带以下辅助工具(slim.utils)

    * async_run 用于初始化数据库连接 ( async_run.py )
    
    * import_path 用于自动导入某一目录下的所有 python 模块 ( autoload.py )
    
    * get_bytes_from_blob 用于从数据库获取到 bytes ( binhex.py )
    
    * to_hex to_bin 用于二进行制和十六进制互转换 ( binhex.py )
    
    * cls_init 提供元类 MetaClassForInit，据此创建的类型会自动调用 cls_init 函数 ( cls_init.py )
    
    * CountDict JsDict 两个侧重不同的计数字典，如slim通过CountDict计算WebSocket数量来统计在线人数 ( count_dict.py )
    
    * json_ex_dumps json.dumps的扩展函数，支持memoryview、bytes、set、DataRecord，已应用于框架本身及lcarus ( json_ex.py )
    
    * myobjectid 与 customid 两个侧重不同的12位分布式ID生成器 ( customid.py myobjectid.py )
    
    * state_obj 类似 Enum ( state_obj.py )
    
    * pagination 分页工具，已应用于框架本身 ( pagination.py )
    
    * request 请求工具，可用于测试，里面定义了get/list/update/new/delete接口 ( slim.tools.SlimViewRequest类 )
    
### 限制

* Python 3.6+

* 支持且仅支持 peewee 和 asyncpg

### 其他

* [基础设计](quickstart/design.md)

* [简单例子](quickstart/helloworld.md)
