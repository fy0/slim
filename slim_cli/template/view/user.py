from slim.utils import to_bin
from slim.base.user import BaseAccessTokenUserMixin
from app import app
from model.user import User
from typing import Dict, List
from slim.base.sqlquery import SQLValuesToWrite, DataRecord
from slim.retcode import RETCODE
from slim.support.peewee import PeeweeView
from view import ValidateForm
from wtforms import validators as va, StringField, IntegerField, ValidationError


class UserMixin(BaseAccessTokenUserMixin):
    """ 用户Mixin，用于与View """
    def teardown_user_key(self):
        u: User = self.current_user
        u.key = None
        u.save()

    def get_user_by_key(self, key):
        if not key: return
        try: return User.get_by_token(to_bin(key))
        except: pass


class SigninByEmailForm(ValidateForm):
    """ 邮箱登录验证表单 """
    email = StringField('email', validators=[va.required(), va.Length(3, 30), va.Email()])
    password = StringField('password', validators=[va.required()])


class SigninByNicknameForm(ValidateForm):
    """ 邮箱登录验证表单 """
    nickname = StringField('nickname', validators=[va.required(), va.Length(2, 30)])
    password = StringField('password', validators=[va.required()])


@app.route('user')
class UserView(PeeweeView, UserMixin):
    model = User

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
            account_key = 'nickname'
            va_form_cls = SigninByNicknameForm
            auth_method = User.auth_by_nickname

        # parameters validate
        form = va_form_cls(**post)
        if not form.validate():
            return self.finish(RETCODE.FAILED, form.errors)

        # auth and generate access token
        user = auth_method(post[account_key], post['password'])
        if user:
            user.refresh_token()
            self.setup_user_key(user.token, 30)
            self.finish(RETCODE.SUCCESS, {'id': user.id, 'access_token': user.token})
        else:
            self.finish(RETCODE.FAILED)

    async def before_update(self, raw_post: Dict, values: SQLValuesToWrite, records: List[DataRecord]):
        pass

    @app.route.interface('POST')
    async def signout(self):
        if self.current_user:
            self.teardown_user_key()
            self.finish(RETCODE.SUCCESS)
        else:
            self.finish(RETCODE.FAILED)
