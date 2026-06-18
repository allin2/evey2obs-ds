"""evey2obs package."""

from evey2obs.cleaner import MediaCleaner
from evey2obs.errors import Evey2ObsError
from evey2obs.events import CancelToken, ProgressEvent
from evey2obs.exporters import ObsidianExporter, render_note
from evey2obs.inputs import extract_urls, identify_source
from evey2obs.models import (
    ContentDocument,
    ContentType,
    ErrorCode,
    ExportResult,
    ExtractedText,
    ExtractionMethod,
    ImageRef,
    ResolvedSource,
    Segment,
    SourceInput,
    SourceMetadata,
    SourceType,
    SummaryResult,
    Task,
    TaskStatus,
    TemporaryMedia,
)
from evey2obs.pipeline import ProcessingPipeline
from evey2obs.processors import (
    FFmpegInfo,
    MediaProcessor,
    SummarizationProcessor,
    TranscriptionProcessor,
)
from evey2obs.settings import AppSettings, LLMSettings, ObsidianSettings
from evey2obs.sources import (
    BilibiliAdapter,
    DouyinAdapter,
    LocalFileAdapter,
    WeChatArticleAdapter,
    XiaohongshuAdapter,
    XiaoyuzhouAdapter,
    YouTubeAdapter,
    YtDlpAdapter,
    find_adapter,
    get_adapters,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # Enums
    "ContentType",
    "ErrorCode",
    "ExtractionMethod",
    "SourceType",
    "TaskStatus",
    # Value objects
    "ImageRef",
    "Segment",
    # Pipeline contracts
    "ResolvedSource",
    "SourceInput",
    "SourceMetadata",
    "ExtractedText",
    "TemporaryMedia",
    "ContentDocument",
    "SummaryResult",
    "ExportResult",
    # Mutable task tracker
    "Task",
    # Settings
    "AppSettings",
    "LLMSettings",
    "ObsidianSettings",
    # Pipeline
    "ProcessingPipeline",
    # Processors
    "FFmpegInfo",
    "MediaProcessor",
    "TranscriptionProcessor",
    "SummarizationProcessor",
    # Exporters
    "ObsidianExporter",
    "render_note",
    # Inputs
    "extract_urls",
    "identify_source",
    # Sources
    "BilibiliAdapter",
    "DouyinAdapter",
    "LocalFileAdapter",
    "WeChatArticleAdapter",
    "XiaohongshuAdapter",
    "XiaoyuzhouAdapter",
    "YouTubeAdapter",
    "YtDlpAdapter",
    "find_adapter",
    "get_adapters",
    # Cleaner
    "MediaCleaner",
    # Errors & events
    "Evey2ObsError",
    "CancelToken",
    "ProgressEvent",
]
