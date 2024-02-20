class Database:
    pass


class MemoryDB(Database):

    def __init__(self, name):
        self.name = name
        self._threads = {}

    async def get_thread_id(self, user) -> int:
        return self._threads.get(user.id)

    async def set_thread_id(self, user, thread_id: int) -> None:
        self._threads[user.id] = thread_id
