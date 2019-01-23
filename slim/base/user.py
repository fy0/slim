from abc import abstractmethod
from typing import Type


class BaseUser:
    """
    用户数据类应继承于此类，举例：

    class User(BaseModel, BaseUser):
        id = BlobField(primary_key=True)
        email = CharField(index=True, max_length=128)
        password = BlobField()

    """

    @property
    def roles(self):
        return {None}


class BaseUserViewMixin:
    """
    应继承此类并实现自己的 UserMixin：

    from model.user import User

    class UserViewMixin(BaseUserMixin):
        @property
        def user_cls(self) -> Type[BaseUser]:
            return User

    """

    @abstractmethod
    def get_current_user(self):
        """Override to determine the current user from, e.g., a cookie."""
        pass

    @abstractmethod
    def get_user_by_key(self, key):
        pass

    @abstractmethod
    def setup_user_key(self, key, expires=30):
        """ setup user key for server """
        pass

    @abstractmethod
    def teardown_user_key(self):
        """ teardown user key for server, make the token invalid here"""
        pass


# noinspection PyAbstractClass
class BaseSecureCookieUserViewMixin(BaseUserViewMixin):
    def get_current_user(self):
        try:
            key = self.get_secure_cookie('u')
            if key:
                return self.get_user_by_key(key)
        except:
            self.del_cookie('u')

    def setup_user_key(self, key, expires=30):
        self.set_secure_cookie('u', key, max_age=expires)

    def teardown_user_key(self):
        self.del_cookie('u')


# noinspection PyAbstractClass
class BaseAccessTokenUserViewMixin(BaseUserViewMixin):
    def get_current_user(self):
        access_token = self.headers.get('AccessToken', None)
        if access_token: return self.get_user_by_key(access_token)

    def setup_user_key(self, key, expires=30):
        pass


# noinspection PyAbstractClass
class BaseAccessTokenInParamUserViewMixin(BaseUserViewMixin):
    def get_current_user(self):
        access_token = self.params.get('AccessToken', None)
        if access_token: return self.get_user_by_key(access_token)

    def setup_user_key(self, key, expires=30):
        pass
