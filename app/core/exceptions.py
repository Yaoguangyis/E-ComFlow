class AppException(Exception):
    def __init__(self, message: str, code: int = 500):
        self.message = message
        self.code = code

class ProviderException(AppException):
    pass

class ProviderTimeoutException(AppException):
    pass

class ProviderRateLimitException(AppException):
    pass