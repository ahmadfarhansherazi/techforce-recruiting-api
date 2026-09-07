class NormalizationError(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class RecruiterNotFound(Exception):
    def __init__(self, recruiter_id: str) -> None:
        self.recruiter_id = recruiter_id
        super().__init__(f"unknown recruiter '{recruiter_id}'")


class ImportFileError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)
