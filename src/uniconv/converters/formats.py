"""Format definitions shared by more than one provider. The registry requires that a key
has exactly one definition, so providers import these instead of declaring their own."""

from uniconv.core.converter import Format

# raster images (Pillow) and vector
JPG = Format("jpg", "JPEG", (".jpg", ".jpeg"), ("image/jpeg",))
PNG = Format("png", "PNG", (".png",), ("image/png",))
WEBP = Format("webp", "WebP", (".webp",), ("image/webp",))
GIF = Format("gif", "GIF", (".gif",), ("image/gif",))
BMP = Format("bmp", "BMP", (".bmp",), ("image/bmp",))
TIFF = Format("tiff", "TIFF", (".tif", ".tiff"), ("image/tiff",))
HEIC = Format("heic", "HEIC", (".heic", ".heif"), ("image/heic", "image/heif"), target=False)
SVG = Format("svg", "SVG", (".svg", ".svgz"))  # text/XML: detected by extension
PDF = Format("pdf", "PDF", (".pdf",), ("application/pdf",), source=False)

# tables and trees
CSV = Format("csv", "CSV", (".csv",))
XLSX = Format("xlsx", "Excel", (".xlsx",),
              ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",))
XLS = Format("xls", "Excel 97-2003", (".xls",), ("application/vnd.ms-excel",), target=False)
ODS = Format("ods", "OpenDocument-rekenblad", (".ods",),
             ("application/vnd.oasis.opendocument.spreadsheet",), target=False)
JSON = Format("json", "JSON", (".json",))
YAML = Format("yaml", "YAML", (".yaml", ".yml"))
TOML = Format("toml", "TOML", (".toml",))
XML = Format("xml", "XML", (".xml",))

# text documents and presentations
MD = Format("md", "Markdown", (".md", ".markdown"))
HTML = Format("html", "HTML", (".html", ".htm"))
TEX = Format("tex", "LaTeX", (".tex",))
DOCX = Format("docx", "Word", (".docx",),
              ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",))
DOC = Format("doc", "Word 97-2003", (".doc",), ("application/msword",), target=False)
ODT = Format("odt", "OpenDocument", (".odt",), ("application/vnd.oasis.opendocument.text",))
EPUB = Format("epub", "EPUB", (".epub",), ("application/epub+zip",))
RTF = Format("rtf", "RTF", (".rtf",), ("application/rtf", "text/rtf"))
# plain text has no structure to read, so it is a target only
TXT = Format("txt", "Platte tekst", (".txt",), source=False)
PPTX = Format("pptx", "PowerPoint", (".pptx",),
              ("application/vnd.openxmlformats-officedocument.presentationml.presentation",),
              target=False)
PPT = Format("ppt", "PowerPoint 97-2003", (".ppt",), ("application/vnd.ms-powerpoint",),
             target=False)
ODP = Format("odp", "OpenDocument-presentatie", (".odp",),
             ("application/vnd.oasis.opendocument.presentation",), target=False)
