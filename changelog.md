#### 0.4.10 update 2019.09.08

* Added: Decorator `must_be_role` 

* Fixed: Decorator `cooldown` not work


#### 0.4.9 update 2019.08.28

* Added: Peewee PostgreSQL ArrayField supported

* Added: `BaseView.method`

* Added: `AbstractSQLView.current_interface`


#### 0.4.8 update 2019.08.27

* Changed: Modified return value of `view.params` and `view.post()` to `MultiDict`

* Added: Decorator `require_role`


#### 0.4.7 update 2019.08.25

* Changed: template update


#### 0.4.6 update 2019.08.25

* Changed: template update

* Changed(break): Rename decorator `auth_role` to `request_role`

* Fixed: Correct return value of `view.params` and `view.post()` to `MultiDictProxy`


#### 0.4.5 update 2019.08.24

* Added: `msg` parameter for view.finish

* Changed(break): Changed define of `Ability`

* Changed: Updated cli template

* Changed: Cli generate project with random port


#### 0.4.4 update 2019.08.22

* Added: decorator `auth_role` and decorator generator `get_cooldown_decorator`

* Added: Type hints for UserViewMixin

* Changed(break): Rewrite `BaseUserViewMixin`.

* Changed(break): Python 3.6 required


#### 0.4.3 update 2019.07.23

* Changed: Renamed `XXConverter` to `XXParser`

* Changed: Renamed `EMPTY_PERMISSION` to `NO_PERMISSION`


#### 0.4.2 update 2019.06.12

* Added: `LIST_PAGE_SIZE_CLIENT_LIMIT` for view

* Changed(break): list api does not return `NOT_FOUND` anymore

* Changed(break): Removed `app.route.get` `app.route.post` `app.route.head` and so on

* Fixed: Can not insert record with empty data


#### 0.4.1 update 2019.01.25

* Fixed: compatible with peewee [3.8.2](https://github.com/coleifer/peewee/releases/tag/3.8.2).

* Fixed: slim-cli not work

#### 0.4.0 update 2019.01.24

* Added: `view.temp_storage` for save values during the request

* Added: `app.permission` option, it can be set to `ALL_PERMISSION`, `NO_PERMISSION` or a `Permissions` object

* Added: **`view.current_user` throw a Exception when current View not inherited from `BaseUserViewMixin`**

* Added: Accept 'Application/json' content as post data [#2](https://github.com/fy0/slim/pull/2)

* Added: Application hooks: `on_startup`, `on_shutdown`, `on_cleanup` [#3](https://github.com/fy0/slim/pull/3)

* Added: New finish method `finish_raw(body: bytes, status: int=200, content_type=None)` [#3](https://github.com/fy0/slim/pull/3)

* Changed: `get_current_user` can works with async function

* Changed(break): Renamed `view.current_role` to `view.current_request_role`

* Changed(break): Renamed `view.current_user_roles` to `view.roles`

* Changed(break): Renamed `BaseUserMixin` to `BaseUserViewMixin`

* Changed(break): Renamed `BaseSecureCookieUserMixin` to `BaseSecureCookieUserViewMixin`

* Changed(break): Renamed `BaseAccessTokenUserMixin` to `BaseAccessTokenUserViewMixin`

* Changed(break): Renamed `BaseAccessTokenInParamUserMixin` to `BaseAccessTokenInParamUserViewMixin`

* Changed(break): Renamed `app.permissions` to `app.table_permissions`

* Removed(break): `view.permission_init` function

* Changed: template update

* Fixed: compatible with current aiohttp version (3.5).

* Fixed: `psycopg2` not required for `PeeweeView`


#### 0.3.14 update 2018.11.14

* Added: the keys startswith '$' in params and postdata will be ignore for database query.

* Changed: `prepare` and `on_finish` method mustn't be an async function anymore.

* Changed: callbacks of insert(`view.before_insert` and `view.after_insert`) changed. It's a break change.

* Fixed: a critical permission bug for all versions, upgrade immediately!!!


#### 0.3.13 update 2018.10.07

* Added: `BaseView.get_x_forwarded_for` method

* Added: `BaseView.get_ip` method

* Changed: Use IOCP eventloop by default on windows system

* Fixed: query operator IS_NOT works


#### 0.3.12 update 2018.09.27

* Added: a new return code named `TOO_FREQUENT`


#### 0.3.11 update 2018.06.03

* Fixed: permission check for records after select remove some columns added by `add_query_condition`.


#### 0.3.10 update 2018.06.01

* Changed: `new` and `set` now accept empty values instead of throw exception.

* Fixed: `SlimExceptions` raised by BaseView.prepare were not caught.

* Fixed: `ErrorCatchContext` didn't catch the ``FinishQuitException`.
