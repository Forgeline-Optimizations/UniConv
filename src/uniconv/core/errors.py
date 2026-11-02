"""Expected failures. str(exc) is always a Dutch message the user can read as-is."""


class UniconvError(Exception):
    """Base class. str(exc) is always a user-facing message."""


class UnsupportedFormatError(UniconvError):
    """Format not known at all."""


class WrongFamilyError(UniconvError):
    """E.g. an MP3 dropped while "image" is selected."""


class UnsupportedConversionError(UniconvError):
    """The source/target pair is not offered."""


class ConversionError(UniconvError):
    """Engine failed, content can't be mapped, or the result can't be written."""


class ToolMissingError(UniconvError):
    """pandoc/ffmpeg not found."""


class ConversionCancelled(UniconvError):
    pass


class InputTooLargeError(UniconvError):
    pass
