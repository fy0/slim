#### 0.3.12 update 2018.09.27

* Added: a new return code named `TOO_FREQUENT`


#### 0.3.11 update 2018.06.03

* Fixed: permission check for records after select remove some columns added by `add_query_condition`.


#### 0.3.10 update 2018.06.01

* Adjusted: `new` and `set` now accept empty values instead of throw exception.

* Fixed: `SlimExceptions` raised by BaseView.prepare were not caught.

* Fixed: `ErrorCatchContext` didn't catch the ``FinishQuitException`.
