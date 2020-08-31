import typing

Message = typing.MutableMapping[str, typing.Any]
Scope = typing.MutableMapping[str, typing.Any]
Receive = typing.Callable[[], typing.Awaitable[Message]]
Send = typing.Callable[[Message], typing.Awaitable[None]]
WSRespond = typing.Callable[[str, bytes], typing.Awaitable[None]]
