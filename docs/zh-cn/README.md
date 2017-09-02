
## 关于

> slim 是一个探索性质 python web 后端框架，它能够直接将 SQL 数据表直接绑定为 web 接口，并配有一个基于角色的管理权限模块。


### 特性

* 基于 aiohttp，全异步请求

* 映射数据表的增删改查为 web 接口

* 支持 url 路由装饰器 @route

* 简单的 session 支持

* 强大的权限管理

* 自带分页工具

### 限制

* Python 3.5+

* 支持且仅支持 peewee 和 asyncpg，能够自动发现表结构

### 其他

* [基础设计](quickstart/design.md)

* [简单例子](quickstart/helloworld.md)
