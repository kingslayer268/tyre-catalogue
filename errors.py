class ExtractorError(Exception):
    """Base Exception for any error with the extractor"""


class FileError(ExtractorError):
    """Error raised if a file type not supported is supplied to the extractor"""

class MissingFieldError(ExtractorError):
    """Error raised if a field is missing"""

class TyreDataParsingError(ExtractorError):
    """Error raised if there is any problem in parsing tyre data"""

class DatabaseError(Exception):
    """Base Exception for any error with the extractor"""

class UserAlreadyExists(DatabaseError):
    """Error raised during user creation if user already exists"""

