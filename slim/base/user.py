from abc import abstractmethod
from typing import Type


class BaseUser:
    """
    用户数据类应继承于此类，并实现对应接口，举例：

    class User(BaseModel, BaseUser):
        id = BlobField(primary_key=True)
        email = CharField(index=True, max_length=128)
        password = BlobField()

        @classmethod
        def get_by_key(cls, key):
            try:
                return cls.get(cls.key == key)
            except DoesNotExist:
                return None

    """
    def __init__(self):
        self.roles = {None}

    @classmethod
    @abstractmethod
    def get_by_key(cls, key) -> "BaseUser":
        pass


class BaseUserMixin:
    """
    应继承此类并实现自己的 UserMixin：

    from model.user import User

    class UserMixin(BaseUserMixin):
        @property
        def user_cls(self) -> Type[BaseUser]:
            return User

    """

    @property
    @abstractmethod
    def user_cls(self) -> Type[BaseUser]:
        pass

    def get_current_user(self):
        try:
            key = self.get_secure_cookie('u')
            if key:
                return self.user_cls.get_by_key(key)
        except:
            self.del_cookie('u')
