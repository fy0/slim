import binascii

from slim.base.view import BaseView
from slim.utils import sentinel, to_bin
from slim.base.user import BaseAccessTokenUserViewMixin, BaseUserViewMixin, BaseUser
from app import app
from model.user import User
from typing import Dict, List, Union, Type
from slim.base.sqlquery import SQLValuesToWrite, DataRecord
from slim.retcode import RETCODE
from slim.support.peewee import PeeweeView

from model.user_token import UserToken
from view import ValidateForm
from wtforms import validators as va, StringField, IntegerField, ValidationError


class UserMixin(BaseAccessTokenUserViewMixin):
    """ 用户Mixin，用于与View """
    @property
    def user_cls(self):
        return User

    def get_user_by_token(self: Union['BaseUserViewMixin', 'BaseView'], token) -> Type[BaseUser]:
        t = UserToken.get_by_token(token)
        if t: return User.get_by_pk(t.user_id)

    async def setup_user_token(self, user_id, key=None, expires=30):
        """ setup user token """
        t = UserToken.new(user_id)
        await t.init(self)
        return t

    def teardown_user_token(self: Union['BaseUserViewMixin', 'BaseView'], token=sentinel):
        """ invalidate the token here"""
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


class SigninByEmailForm(ValidateForm):
    """ 邮箱登录验证表单 """
    email = StringField('email', validators=[va.required(), va.Length(3, 30), va.Email()])
    password = StringField('password', validators=[va.required()])


class SigninByUsernameForm(ValidateForm):
    """ 用户名登录验证表单 """
    username = StringField('username', validators=[va.required(), va.Length(2, 30)])
    password = StringField('password', validators=[va.required()])


class SignupForm(ValidateForm):
    """ 注册验证表单 """
    username = StringField('username', validators=[va.required(), va.Length(2, 30)])
    email = StringField('email', validators=[va.optional(), va.Length(3, 30), va.Email()])
    password = StringField('password', validators=[va.required()])


@app.route('user')
class UserView(PeeweeView, UserMixin):
    model = User

    @classmethod
    def interface(cls):
        super().interface()
        cls.discard('new')
        cls.discard('delete')

    @app.route.interface('POST')
    async def signup(self):
        """ 创建账户 """
        data = await self.post_data()

        form = SignupForm(**data)
        if not form.validate():
            return self.finish(RETCODE.INVALID_POSTDATA, form.errors)

        u = User.new(data['username'], data['password'], email=data.get('email', None), nickname=data.get('nickname', None))
        if not u:
            self.finish(RETCODE.FAILED, msg='注册失败！')
        else:
            t: UserToken = await self.setup_user_token(u.id)
            self.finish(RETCODE.SUCCESS, {'id': u.id, 'username': u.username, 'access_token': t.get_token()})

    @app.route.interface('POST')
    async def signin(self):
        # get post data
        post = await self.post_data()
        use_mail = post.get('email', None)

        # check auth method
        if use_mail:
            account_key = 'email'
            va_form_cls = SigninByEmailForm
            auth_method = User.auth_by_mail
        else:
            account_key = 'username'
            va_form_cls = SigninByUsernameForm
            auth_method = User.auth_by_username

        # parameters validate
        form = va_form_cls(**post)
        if not form.validate():
            return self.finish(RETCODE.FAILED, form.errors)

        # auth and generate access token
        user = auth_method(post[account_key], post['password'])
        if user:
            t: UserToken = await self.setup_user_token(user.id)
            self.finish(RETCODE.SUCCESS, {'id': user.id, 'access_token': t.get_token()})
        else:
            self.finish(RETCODE.FAILED, msg='用户名或密码不正确')

    @app.route.interface('POST')
    async def signout(self):
        if self.current_user:
            self.teardown_user_token()
            self.finish(RETCODE.SUCCESS)
        else:
            self.finish(RETCODE.FAILED)

    async def before_update(self, raw_post: Dict, values: SQLValuesToWrite, records: List[DataRecord]):
        pass
