import aiogram.types as agtypes


class Database:
    pass


class MemoryDb(Database):

    def __init__(self, name: str):
        self.name = name
        self._threads = {}
        self._bans = {}

    async def get_thread_id(self, user: agtypes.User) -> int:
        return self._threads.get(user.id)

    async def get_user_id(self, thread_id: int) -> int:
        for k, v in self._threads.items():
            if v == thread_id:
                return k

    async def set_thread_id(self, user: agtypes.User, thread_id: int) -> None:
        self._threads[user.id] = thread_id


class SqlDb(Database):

    def __init__(self, name: str):
        ...

    async def get_thread_id(self, user: agtypes.User) -> int:
        ...

    async def get_user_id(self, thread_id: int) -> int:
        ...

    async def set_thread_id(self, user: agtypes.User, thread_id: int) -> None:
        ...
