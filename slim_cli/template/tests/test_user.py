import pytest
from api.user import UserView
from app import app
from slim.retcode import RETCODE
from slim.tools.test import invoke_interface
from slim.utils import to_hex


async def test_user_signin_empty_post():
    resp = await invoke_interface(app, UserView.signin, post={})
    assert resp.ret_val['code'] == RETCODE.INVALID_POSTDATA


async def test_user_signin_success():
    resp = await invoke_interface(app, UserView.signin, post={'username': '_test_user_1', 'password': 'password'})
    assert resp.ret_val['code'] == RETCODE.SUCCESS
    assert 'access_token' in resp.ret_val['data']
    return resp.ret_val


async def test_user_signin_failed_no_user():
    resp = await invoke_interface(app, UserView.signin, post={'password': 'password'})
    assert resp.ret_val['code'] == RETCODE.FAILED


async def test_user_signin_signin_email():
    resp = await invoke_interface(app, UserView.signin, post={'email': 'test@mail.com', 'password': 'password'})
    assert resp.ret_val['code'] == RETCODE.FAILED


async def test_user_signout():
    user_info = await test_user_signin_success()
    resp = await invoke_interface(app, UserView.signout, headers={'AccessToken': to_hex(user_info['data']['access_token'])})
    assert resp.ret_val['code'] == RETCODE.SUCCESS


async def test_user_signout_failed():
    resp = await invoke_interface(app, UserView.signout, headers={'AccessToken': '1122'})
    assert resp.ret_val['code'] == RETCODE.FAILED
