"""Safe errors: details are fixed operator instructions, never provider exceptions."""


class SetupError(RuntimeError):
    def __init__(self, code, action):
        self.code = code
        self.action = action
        super().__init__(action)

    def report(self):
        return {"status": "failed", "code": self.code, "action": self.action}
