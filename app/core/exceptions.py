from fastapi import HTTPException, status


class GeospatialAPIException(HTTPException):
    """Base API Exception for Geospatial Service."""
    def __init__(self, status_code: int, detail: str):
        super().__init__(status_code=status_code, detail=detail)


class FileRecordNotFoundException(GeospatialAPIException):
    def __init__(self, file_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with ID '{file_id}' not found."
        )


class InvalidFileFormatException(GeospatialAPIException):
    def __init__(self, message: str = "Invalid file format. Only .zip (Shapefiles) and .kml are supported."):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )


class CorruptFileException(GeospatialAPIException):
    def __init__(self, message: str = "Failed to parse geospatial file. File may be corrupted or malformed."):
        super().__init__(
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            detail=message
        )


class FileTooLargeException(GeospatialAPIException):
    def __init__(self, max_bytes: int):
        super().__init__(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {max_bytes / (1024 * 1024):.1f} MB."
        )
