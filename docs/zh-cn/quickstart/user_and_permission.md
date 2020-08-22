# 用户和权限

## 用户对象

`BaseView` 中预留了 `current_user` 对象，当能够确认访问者具有用户权限后，`current_user`会返回用户对象。

从 `XXXUserViewMixin` 派生继承就可以实现用户机制，一段例子(slim cli创建的项目，api/view.py)：

```python
@app.route.view('user')
class UserView(PeeweeView, UserMixin):
    model = User

    @app.route.interface('POST')
    async def signout(cls):
        if cls.current_user:
            cls.teardown_user_token()
            cls.finish(RETCODE.SUCCESS)
        else:
            cls.finish(RETCODE.FAILED)
```

这里 `UserView` 派生自 `PeeweeView` 和 `UserMixin`，后者就是关键，来看其实现：

```python
from slim.base.user import BaseAccessTokenUserViewMixin, BaseUserViewMixin, BaseUser


class UserMixin(BaseAccessTokenUserViewMixin):
    """ 用户Mixin，用于View继承 """

    @property
    def user_cls(cls):
        return User

    def get_user_by_token(cls: Union['BaseUserViewMixin', 'BaseView'], token) -> Type[BaseUser]:
        """ 获得 token 对应的用户对象 """
        t = UserToken.get_by_token(token)
        if t: return User.get_by_pk(t.user_id)

    async def setup_user_token(cls, user_id, key=None, expires=30):
        """ 登录成功后，新建一个 token """
        t = UserToken.new(user_id)
        await t.init(cls)
        return t

    def teardown_user_token(cls: Union['BaseUserViewMixin', 'BaseView'], token=sentinel):
        """ 注销，使 token 失效 """
        u = cls.current_user
        if u:
            if token is None:
                # clear all tokens
                UserToken.delete().where(UserToken.user_id == u.id).execute()
                return

            if token is sentinel:
                try:
                    token = to_bin(cls.get_user_token())
                except binascii.Error:
                    return
            UserToken.delete().where(UserToken.user_id == u.id, UserToken.id == token).execute()
```

这段代码主要围绕 `UserToken` 这个表展开，我们看下其核心定义：

```python
class UserToken(BaseModel):
    id = BlobField(primary_key=True)
    user_id = BlobField(index=True)
```

`BlobField` 对应一个hex字串，例如 `1234abcd`，构成与用户ID的对应关系。

一个用户可以有多个token，每一个都可以取得用户权限，这样能够支持多端同时登录。


## 权限描述

slim 支持一个基于角色的权限(RBAC)系统。

这个权限系统的根在`Application`对象上，即`app.permission`

默认值为`None`或`EMPTY_PERMISSION`（这是一个特殊常量），代表无任何权限。

开发初期可设置为`ALL_PERMISSION`，代表拥有完全权限，从而可以先实现逻辑，验证想法，再进行权限方面的控制。

这两个特殊值定义在`slim.base.permission`，如下：

```python
ALL_PERMISSION = object()
EMPTY_PERMISSION = object()
```

slim的权限系统作用于和`AbstractSQLView`关联的数据表，并影响`AbstractSQLView`定义的若干个系统接口。

对于数据表中的每一个列（Column），提供以下五种权限：

```python
class A:
    QUERY = 'query'  # 查询权限，有此权限的列可以作为查询条件，并使用运算符。影响除new之外的全部默认接口
    READ = 'read'  # 读取权限，影响客户端能看到的数据，同样影响returning为true情况下的返回值。影响delete之外的全部接口。
    WRITE = 'write'  # 写入权限。特别的，写入和创建权限是分离的，请注意这一点。影响set接口。
    CREATE = 'create'  # 创建权限，影响new接口。
    DELETE = 'delete'  # delete权限，影响delete接口。

    ALL = {QUERY, READ, WRITE, CREATE, DELETE}
```

下面是一个示例：

```python
from slim.base.permission import Ability, A, DataRecord

visitor = Ability({
    'test': {
        '*': {A.QUERY},  # 默认权限(见下)
        '|': {A.CREATE},  # 叠加权限(见下)
        'id': {A.READ},
    },
    'topic': {
        'id': {A.QUERY, A.READ},
        'state': {A.READ,},
        'visible': {A.READ,},
        'time': {A.READ,},
        'user_id': {A.QUERY, A.READ},

        'title': {A.READ,},
        'board_id': {A.QUERY, A.READ},

        'edit_count': {A.READ,},
        'edit_time': {A.READ,},
        'last_edit_user_id': {A.READ,},
        'content': {A.READ,},

        'awesome': {A.READ,},
        'sticky_weight': {A.QUERY, A.READ,},
        'weight': {A.READ,},
        'update_time': {A.READ,},
    },
})

app.permission.add(None, visitor)
```

这个例子中定义了visitor这一角色， 并描述了两个表的具体权限。

我们看到对visitor（未登录的访问者）来说 topic 是只读的，并能够基于主题id、主题作者、所属版面id等条件做查询操作。

不能新建也不能删除。

而对 test 表，id这一项是可读的之外，还涉及两个特殊权限：

1. 默认权限 '*'

    默认权限作用的范围是指定表的全部列，`'*': {A.QUERY}`的意思是这个数据表的所有列只要不额外写出，都拥有 Query 权限。

    但是一旦额外做出定义，就会覆盖掉默认权限，例如test表对id列做了额外定义，那么id这一列就只能读取，而不能作为条件进行查询。

2. 叠加权限 '|'

    叠加权限作用的范围也是指定表的全部列，但与默认权限不同，他会在对现有权限声明的基础上进行“叠加”操作。

    请注意，没有明确声明的列，也在叠加权限的影响范围之内。因此test表id的权限最终为 {A.READ, A.CREATE}，其余列的权限为{A.READ, A.QUERY, A.CREATE}。

如果在具体操作时，没能通过相应的权限检查，会对应以下行为：

QUERY: 忽略无权限的列，不报错

READ: 忽略无权限的列，不报错（即使查询时进行了select）

WRITE: 忽略无权限的列，不报错

CREATE: 要求全部列拥有 CREATE 权限，否则报错

DELETE: 要求全部列拥有 DELETE 权限，否则报错

此外，权限系统中其实有几个钩子可以实现ACL控制，但是在实践中发现和`before_query`有所重叠，而且设计的也并不好。因此这几个隶属于`Ability`类的函数会在后面重做，也尽量避免使用，这里就不展开讲了。

如有兴趣自己读一下`slim.base.permission.Ability`的源码吧。


## 角色

角色是RBAC权限系统的核心，slim允许一个用户拥有多个角色。

刚才的例子中，我们展示了一个vistor角色的定义例子。

通常这个角色指的是站点的访问者（无论是已经登录还是未登录，都拥有vistor权限）。

### 角色的继承

现在我们可以定义一个站点用户角色 `user`：

```python
normal_user = Ability({
    'topic': {
        '|': {A.CREATE},
        'title': {A.READ, A.WRITE},
        'board_id': {A.QUERY, A.READ},
        'content': {A.READ, A.WRITE},
    },
}, based_on=visitor)

app.permission.add('user', user)
```

我们可以从代码中看出，`user`角色是基于`visitor`角色的，同时这一角色可以创建主题了。此外还可以编辑主题的标题、正文和所属版面。

请注意一点，角色权限的继承，会继承新的角色定义中未提到的部分。如果某一列双方都有提到，那么新的角色对那一列的定义会**完全覆盖**之前的。

例如，`user`的`topic`中`title`这一权限，定义为`'title': {A.READ, A.WRITE}`，会完全覆盖之前的定义`'title': {A.READ}`。如果之前定义为`'title': {A.READ, A.QUERY}`，那么`QUERY`这一权限在`user`角色下将完全不存在。

此外，默认权限`'*'`和叠加权限`'|'`也会被覆盖。注意它们会在覆盖完成后进行统一结算（也就是都以最下层的一个为准）。而不是先结算上一级角色的默认和叠加，再把结果和第二级的权限定义进行结合。

完成角色定义后用`app.permission.add`做一个添加。

### 扮演角色

由于一个用户允许拥有多个角色，slim 也不会自动帮用户选择角色。

因此客户端在发起请求的时候，应当声明自己在当前操作下想要扮演的角色。

具体的方式是在请求头中添加`Role: the-role-you-want`，例如`Role: user`

这样一来，slim会首先检查你是否拥有这一角色，如果拥有，你就可以使用这一角色的权限来进行操作了。

理论上所有的访问者都拥有基本角色visitor。因此在不填写的时候，默认角色就是None(即visitor)。

也就是说，同一个接口在不同权限下会返回不同的数据，具体内容可以自定义。

这也避免了高权限的管理员用户在获取主题的作者信息时，如果默认以最高权限直接访问会带出大量的特殊信息的问题。
