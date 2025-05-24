class AppError(Exception):
    def __init__(self, message: str, status_code: int):
        """
        Custom exception class for application errors.

        Args:
            message (str): The error message.
            status_code (int): The HTTP status code associated with the error.
        """
        super().__init__(message)

        self.status_code = status_code
        self.status = "fail" if str(status_code).startswith("4") else "error"
        self.is_operational = True
        # Stack trace is automatically captured by Python's exception mechanism