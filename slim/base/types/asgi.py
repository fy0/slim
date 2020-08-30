import typing

Message = typing.MutableMapping[str, typing.Any]
Scope = typing.MutableMapping[str, typing.Any]
Receive = typing.Callable[[], typing.Awaitable[Message]]
Send = typing.Callable[[Message], typing.Awaitable[None]]
WSRespond = typing.Callable[[typing.Optional[str], typing.Optional[bytes]], typing.Awaitable[None]]
