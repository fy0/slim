import hashlib
import os
import time
import traceback
from typing import Set, Optional

import peewee
from peewee import *
from slim.base.user import BaseUser
from slim.utils import StateObject, CustomID, get_bytes_from_blob
from permissions.role_define import ACCESS_ROLE

import config
from model import db, StdBaseModel, CITextField, get_time


class POST_STATE(StateObject):
    DEL = 0
    APPLY = 20  # 等待发布审核
    CLOSE = 30  # 禁止回复
    NORMAL = 50

    txt = {DEL: "删除", APPLY: '待审核', CLOSE: "锁定", NORMAL: "正常"}


class User(StdBaseModel, BaseUser):
    email = TextField(index=True, unique=True, null=True, default=None)
    username = CITextField(index=True, unique=True, null=True)

    nickname = TextField(index=True, null=True)
    password = BlobField()
    salt = BlobField()

    state = IntegerField(default=POST_STATE.NORMAL, index=True)  # 当前状态

    class Meta:
        db_table = 'user'

    @property
    def roles(self) -> Set:
        """
        BaseUser.roles 的实现，返回用户可用角色
        :return:
        """
        ret = {None}
        if self.state == POST_STATE.DEL:
            return ret
        ret.add(ACCESS_ROLE.USER)
        return ret

    @classmethod
    def new(cls, username, password, *, email=None, nickname=None, is_for_tests=False) -> Optional['User']:
        values = {
            'email': email,
            'username': username,
            'nickname': nickname,
            'is_for_tests': is_for_tests,

            # 被default自动生成
            # 'id': CustomID().to_bin(),
            # 'time': int(time.time()),
        }

        info = cls.gen_password_and_salt(password)
        values.update(info)

        try:
            uid = User.insert(values).execute()
            u = User.get_by_pk(uid)
            return u
        except peewee.IntegrityError as e:
            # traceback.print_exc()
            db.rollback()
            if e.args[0].startswith('duplicate key'):
                return
        except peewee.DatabaseError:
            traceback.print_exc()
            db.rollback()

    @classmethod
    def gen_password_and_salt(cls, password_text):
        """ 生成加密后的密码和盐 """
        salt = os.urandom(32)
        dk = hashlib.pbkdf2_hmac(
            config.PASSWORD_HASH_FUNC_NAME,
            password_text.encode('utf-8'),
            salt,
            config.PASSWORD_HASH_ITERATIONS,
        )
        return {'password': dk, 'salt': salt}

    def set_password(self, new_password):
        """ 设置密码 """
        info = self.gen_password_and_salt(new_password)
        self.password = info['password']
        self.salt = info['salt']
        self.save()

    def _auth_base(self, password_text):
        """
        已获取了用户对象，进行密码校验
        :param password_text:
        :return:
        """
        dk = hashlib.pbkdf2_hmac(
            config.PASSWORD_HASH_FUNC_NAME,
            password_text.encode('utf-8'),
            get_bytes_from_blob(self.salt),
            config.PASSWORD_HASH_ITERATIONS
        )

        if get_bytes_from_blob(self.password) == get_bytes_from_blob(dk):
            return self

    @classmethod
    def auth_by_mail(cls, email, password_text):
        try: u = cls.get(cls.email == email)
        except DoesNotExist: return False
        return u._auth_base(password_text)

    @classmethod
    def auth_by_username(cls, username, password_text):
        try: u = cls.get(cls.username == username)
        except DoesNotExist: return False
        return u._auth_base(password_text)

    def __repr__(self):
        if isinstance(self.id, (bytes, memoryview)):
            return '<User id:%x username:%r>' % (int.from_bytes(get_bytes_from_blob(self.id), 'big'), self.username)
        elif isinstance(self.id, int):
            return '<User id:%d username:%r>' % (self.id, self.username)
        else:
            return '<User id:%s username:%r>' % (self.id, self.username)
