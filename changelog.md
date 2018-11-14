
#### 0.3.14 update 2018.11.14

* Added: the keys startswith '$' in params and postdata will be ignore for database query.

* Adjusted: `prepare` and `on_finish` method mustn't be an async function anymore.

* Adjusted: callbacks of insert(`view.before_insert` and `view.after_insert`) changed. It's a break change.

* Fixed: a critical permission bug for all versions, upgrade immediately!!!


#### 0.3.13 update 2018.10.07

* Added: `BaseView.get_x_forwarded_for` method

* Added: `BaseView.get_ip` method

* Adjusted: Use IOCP eventloop by default on windows system

* Fixed: query operator IS_NOT works


#### 0.3.12 update 2018.09.27

* Added: a new return code named `TOO_FREQUENT`


#### 0.3.11 update 2018.06.03

* Fixed: permission check for records after select remove some columns added by `add_query_condition`.


#### 0.3.10 update 2018.06.01

* Adjusted: `new` and `set` now accept empty values instead of throw exception.

* Fixed: `SlimExceptions` raised by BaseView.prepare were not caught.

* Fixed: `ErrorCatchContext` didn't catch the ``FinishQuitException`.
