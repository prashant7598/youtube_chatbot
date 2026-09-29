"""User-safe error types. Internal exception details are never sent to the browser."""

from __future__ import annotations


class AppError(Exception):
    status_code = 400
    code = "request_failed"
    public_message = "The request could not be completed."

    def __init__(self, public_message: str | None = None) -> None:
        super().__init__(public_message or self.public_message)
        self.public_message = public_message or self.public_message


class InvalidVideoUrlError(AppError):
    code = "invalid_video_url"
    public_message = "Enter a valid YouTube video URL or 11-character video ID."


class TranscriptUnavailableError(AppError):
    status_code = 422
    code = "transcript_unavailable"
    public_message = "This video has no usable captions in the requested languages."


class TranscriptBlockedError(AppError):
    status_code = 503
    code = "youtube_request_blocked"
    public_message = "YouTube is temporarily blocking transcript requests from this server. Please try again later."


class VideoUnavailableError(AppError):
    status_code = 404
    code = "video_unavailable"
    public_message = "The video is unavailable or cannot be accessed."


class ConfigurationError(AppError):
    status_code = 503
    code = "service_not_configured"


class ExternalServiceError(AppError):
    status_code = 502
    code = "external_service_error"
    public_message = "A required service did not respond correctly. Please try again."


class VideoNotIndexedError(AppError):
    status_code = 409
    code = "video_not_indexed"
    public_message = "Load this video before asking a question."


class InvalidSessionError(AppError):
    code = "invalid_session"
    public_message = "The chat session is invalid. Start a new chat and try again."


class UnsafePromptError(AppError):
    code = "unsafe_prompt"
    public_message = "I can only help with questions about the current video's transcript."
