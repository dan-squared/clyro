from pathlib import Path
from clyro.core.types import Result, MediaType
from clyro.errors import ConversionNotPossibleError

class ConvertDispatcher:
    def __init__(self, image_image, image_pdf, video_video, video_image, pdf_image, pdf_doc):
        self.handlers = {
            # Map (src_type, tgt_format_type) -> Handler class
            ("image", "image"): image_image,
            ("image", "document"): image_pdf,
            ("video", "video"): video_video,
            ("video", "image"): video_image,
            ("document", "image"): pdf_image,
            ("document", "document"): pdf_doc
        }
        
    def convert(self, source: Path, target_format: str, out_path: Path, src_type: MediaType, tgt_type: str, signals, job: 'Job') -> Result:
        src_str = "image" if src_type == MediaType.IMAGE else ("video" if src_type == MediaType.VIDEO else "document")
        key = (src_str, tgt_type)
        
        handler = self.handlers.get(key)
        if not handler:
            raise ConversionNotPossibleError(f"Cannot convert {src_str} to {tgt_type}")
            
        return handler.convert(source, target_format, out_path, signals, job)

    def merge_to_pdf(self, sources: list[Path], out_path: Path, src_type: MediaType, signals, job: 'Job') -> Result:
        src_str = "image" if src_type == MediaType.IMAGE else ("video" if src_type == MediaType.VIDEO else "document")
        # Currently we only support merging images into a PDF
        if src_str != "image":
            raise ConversionNotPossibleError(f"Cannot merge {src_str} into PDF")
            
        handler = self.handlers.get(("image", "document"))
        if not handler or not hasattr(handler, "merge"):
            raise ConversionNotPossibleError("Image to PDF merge handler not available")
            
        return handler.merge(sources, out_path, signals, job)
