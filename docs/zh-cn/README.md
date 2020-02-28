
## 关于

> slim 是一个探索性质 python web 后端框架（底层基于aiohttp），它能够直接将 SQL 数据表直接绑定为 web 接口，并配有一个基于角色与数据表的管理权限模块。


### 特性

* 基于 aiohttp，全异步请求

* 映射数据表的增删改查为 web 接口

* 支持 url 路由装饰器 @route

* 简单的 session 支持

* 基于数据表的权限管理

* 简单命令行工具slim init，可用于初始化项目目录


### 限制

* Python 3.6+

* 目前仅支持 peewee 作为 ORM


### 其他

* [基础设计](quickstart/_design.md)

* [简单例子](quickstart/helloworld.md)
