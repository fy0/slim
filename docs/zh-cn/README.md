
## 关于

> slim 是一个探索性质 python web 后端框架（底层基于aiohttp），它能够直接将 SQL 数据表直接绑定为 web 接口，并配有一个基于角色与数据表的管理权限模块。


### 特性

* 基于 aiohttp，全异步请求

* 映射数据表的增删改查为 web 接口

* 支持 url 路由装饰器 @route

* 简单的 session 支持

* 基于数据表的权限管理

* 附带以下辅助工具(slim.utils)

    * pagination 分页工具，已应用于框架本身
    
    * myobjectid 与 customid 两个侧重不同的12位分布式ID生成器

    * state_obj 类似 Enum

    * request 请求工具，可用于测试
    
    * cls_init 提供元类 MetaClassForInit，据此创建的类型会自动调用 cls_init 函数


### 限制

* Python 3.5+

* 支持且仅支持 peewee 和 ~~asyncpg~~(暂时不可用)

### 其他

* [基础设计](quickstart/design.md)

* [简单例子](quickstart/helloworld.md)
