import typing
from abc import abstractmethod
from typing import Union, Type

if typing.TYPE_CHECKING:
    from .view import BaseView


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

    class UserViewMixin(BaseUserViewMixin):
        pass
    """

    def get_current_user(self: Union['BaseUserViewMixin', 'BaseView']):
        key = self.get_user_token()
        if key: return self.get_user_by_token(key)

    @abstractmethod
    def get_user_token(self: Union['BaseUserViewMixin', 'BaseView']):
        """Get access token for specified user"""
        pass

    @abstractmethod
    def get_user_by_token(self: Union['BaseUserViewMixin', 'BaseView'], token) -> Type[BaseUser]:
        pass

    @abstractmethod
    def setup_user_token(self: Union['BaseUserViewMixin', 'BaseView'], user_id, key=None, expires=30):
        """ setup user token """
        pass

    @abstractmethod
    def teardown_user_token(self: Union['BaseUserViewMixin', 'BaseView'], token=None):
        """ invalidate the token here"""
        pass


# noinspection PyAbstractClass
class BaseSecureCookieUserViewMixin(BaseUserViewMixin):
    def get_user_token(self: Union[BaseUserViewMixin, 'BaseView']):
        """Get access token for specified user"""
        try:
            return self.get_secure_cookie('u')
        except:
            self.del_cookie('u')

    def setup_user_token(self: Union[BaseUserViewMixin, 'BaseView'], user_id, key=None, expires=30):
        """ setup user token """
        if key:
            self.set_secure_cookie('u', key, max_age=expires)

    def teardown_user_token(self: Union['BaseUserViewMixin', 'BaseView'], token=None):
        """ invalidate the token here"""
        self.del_cookie('u')


# noinspection PyAbstractClass
class BaseAccessTokenUserViewMixin(BaseUserViewMixin):
    def get_user_token(self: Union[BaseUserViewMixin, 'BaseView']):
        """Get access token for specified user"""
        return self.headers.get('AccessToken', None)
