"""In-memory Redis for the Claude budget gate (mirrors _RESERVE_SCRIPT semantics)."""


class BudgetFakeRedis:
    def __init__(self, store=None, *, broken=False, fail_writes=False):
        self.store = dict(store or {})
        self.broken = broken
        self.fail_writes = fail_writes

    def _check(self, write=False):
        if self.broken or (write and self.fail_writes):
            raise ConnectionError("redis down")

    async def get(self, key):
        self._check()
        return self.store.get(key)

    async def set(self, key, value):
        self._check(True)
        self.store[key] = value

    async def incrby(self, key, amount):
        self._check(True)
        self.store[key] = str(int(float(self.store.get(key, "0"))) + int(amount))
        return int(self.store[key])

    async def decrby(self, key, amount):
        return await self.incrby(key, -int(amount))

    async def incrbyfloat(self, key, amount):
        self._check(True)
        self.store[key] = repr(float(self.store.get(key, "0")) + float(amount))
        return float(self.store[key])

    async def expire(self, key, ttl):
        self._check(True)
        return True

    async def eval(self, script, numkeys, *args):
        # No await inside: atomic with respect to other coroutines, like Lua in Redis.
        self._check()
        keys, argv = args[:numkeys], args[numkeys:]
        used_t = float(self.store.get(keys[0], "0"))
        held_t = float(self.store.get(keys[1], "0"))
        used_c = float(self.store.get(keys[2], "0"))
        held_c = float(self.store.get(keys[3], "0"))
        want_t, want_c = int(argv[0]), float(argv[1])
        if used_t + held_t + want_t > int(argv[2]):
            return 0
        if used_c + held_c + want_c > float(argv[3]):
            return 0
        self.store[keys[1]] = str(int(held_t) + want_t)
        self.store[keys[3]] = repr(held_c + want_c)
        return 1
