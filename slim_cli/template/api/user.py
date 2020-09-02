import binascii
from typing import Union, Type

from slim.base.view import BaseView
from slim.ext.decorator import require_role
from slim.utils import sentinel, to_bin
from slim.base.user import BaseAccessTokenUserViewMixin, BaseUserViewMixin, BaseUser
from slim.retcode import RETCODE
from slim.ext.view.support import PeeweeView

from app import app
from api.validate.user import SigninDataModel, SignupDirectDataModel
from api import run_in_thread
from model.user import User
from model.user_token import UserToken
from permissions.role_define import ACCESS_ROLE


class UserMixin(BaseAccessTokenUserViewMixin):
    """ 用户Mixin，用于View继承 """
    def get_user_by_token(self: Union['BaseUserViewMixin', 'BaseView'], token) -> Type[BaseUser]:
        t = UserToken.get_by_token(token)
        if t: return User.get_by_pk(t.user_id)

    async def setup_user_token(self, user_id, key=None, expires=30):
        """ signin, setup user token """
        t = UserToken.new(user_id)
        await t.init(self)
        return t

    def teardown_user_token(self: Union['BaseUserViewMixin', 'BaseView'], token=sentinel):
        """ signout, invalidate the token here """
        u = self.current_user
        if u:
            if token is None:
                # clear all tokens
                UserToken.delete().where(UserToken.user_id == u.id).execute()
                return

            if token is sentinel:
                # clear current token
                try:
                    token = to_bin(self.get_user_token())
                except binascii.Error:
                    return
            UserToken.delete().where(UserToken.user_id == u.id, UserToken.id == token).execute()


@app.route.view('user', 'User API')
class UserView(PeeweeView, UserMixin):
    model = User

    @classmethod
    def interface_register(cls):
        super().interface_register()
        cls.unregister('new')
        cls.unregister('delete')

    @app.route.interface('POST', summary='注册', va_post=SignupDirectDataModel)
    async def signup(self):
        """
        用户注册接口
        User Signup Interface
        """
        vpost: SignupDirectDataModel = self._.validated_post

        u = User.new(vpost.username, vpost.password, email=vpost.email, nickname=vpost.nickname)
        if not u:
            self.finish(RETCODE.FAILED, msg='注册失败！')
        else:
            t: UserToken = await self.setup_user_token(u.id)
            self.finish(RETCODE.SUCCESS, {'id': u.id, 'username': u.username, 'access_token': t.get_token()})

    @app.route.interface('POST', summary='登录', va_post=SigninDataModel)
    async def signin(self):
        """
        用户登录接口
        User Signin Interface
        """
        vpost: SigninDataModel = self._.validated_post

        # check auth method
        if vpost.email:
            field_value = vpost.email
            auth_method = User.auth_by_mail
        elif vpost.username:
            field_value = vpost.username
            auth_method = User.auth_by_username
        else:
            return self.finish(RETCODE.FAILED, msg='必须提交用户名或邮箱中的一个作为登录凭据')

        # auth and generate access token
        user = await run_in_thread(auth_method, field_value, vpost.password)

        if user:
            t: UserToken = await self.setup_user_token(user.id)
            self.finish(RETCODE.SUCCESS, {'id': user.id, 'access_token': t.get_token()})
        else:
            self.finish(RETCODE.FAILED, msg='用户名或密码不正确')

    @app.route.interface('POST', summary='登出')
    @require_role(ACCESS_ROLE.USER)
    async def signout(self):
        """
        退出登录
        """
        if self.current_user:
            self.teardown_user_token()
            self.finish(RETCODE.SUCCESS)
        else:
            self.finish(RETCODE.FAILED)
