# 用户和权限

## 用户对象

`BaseView` 中预留了 `current_user` 对象，当能够确认访问者具有用户权限后，`current_user`会返回用户对象。

从 `XXXUserViewMixin` 派生继承就可以实现用户机制，一段例子(slim cli创建的项目，api/view.py)：

```python
@app.route.view('user')
class UserView(PeeweeView, UserMixin):
    model = User

    @app.route.interface('POST')
    async def signout(self):
        if self.current_user:
            self.teardown_user_token()
            self.finish(RETCODE.SUCCESS)
        else:
            self.finish(RETCODE.FAILED)
```

这里 `UserView` 派生自 `PeeweeView` 和 `UserMixin`，后者就是关键，来看其实现：

```python
from slim.base.user import BaseAccessTokenUserViewMixin, BaseUserViewMixin, BaseUser


class UserMixin(BaseAccessTokenUserViewMixin):
    """ 用户Mixin，用于View继承 """

    @property
    def user_cls(self):
        return User

    def get_user_by_token(self: Union['BaseUserViewMixin', 'BaseView'], token) -> Type[BaseUser]:
        """ 获得 token 对应的用户对象 """
        t = UserToken.get_by_token(token)
        if t: return User.get_by_pk(t.user_id)

    async def setup_user_token(self, user_id, key=None, expires=30):
        """ 登录成功后，新建一个 token """
        t = UserToken.new(user_id)
        await t.init(self)
        return t

    def teardown_user_token(self: Union['BaseUserViewMixin', 'BaseView'], token=sentinel):
        """ 注销，使 token 失效 """
        u = self.current_user
        if u:
            if token is None:
                # clear all tokens
                UserToken.delete().where(UserToken.user_id == u.id).execute()
                return

            if token is sentinel:
                try:
                    token = to_bin(self.get_user_token())
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

## 角色


## 表权限

