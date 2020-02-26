from schematics import Model
from schematics.types import EmailType, StringType

from slim.base.types.doc import ValidatorDoc


class SigninDataModel(Model):
    email = EmailType(min_length=3, max_length=30, metadata=ValidatorDoc('Email'))
    username = StringType(min_length=2, max_length=30, metadata=ValidatorDoc('Username'))
    password = StringType(required=True, min_length=6, max_length=64, metadata=ValidatorDoc('Password'))


class SignupDataModel(Model):
    email = EmailType(min_length=3, max_length=30, required=True, metadata=ValidatorDoc('Email'))
    username = StringType(min_length=2, max_length=30, metadata=ValidatorDoc('Username'))
    password = StringType(required=True, min_length=6, max_length=64, metadata=ValidatorDoc('Password'))
    nickname = StringType(min_length=2, max_length=10, metadata=ValidatorDoc('Nickname'))
