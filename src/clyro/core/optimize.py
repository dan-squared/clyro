from pathlib import Path
from clyro.core.types import MediaType, Result

class OptimizeDispatcher:
    def __init__(self, image_handler, video_handler, pdf_handler):
        self.image = image_handler
        self.video = video_handler
        self.pdf = pdf_handler
        
    def optimize(self, source: Path, out_path: Path, media_type: MediaType, aggressive: bool, signals, job: 'Job') -> Result:
        if media_type == MediaType.IMAGE:
            return self.image.optimize(source, out_path, aggressive, signals, job)
        elif media_type == MediaType.VIDEO:
            return self.video.optimize(source, out_path, aggressive, signals, job)
        elif media_type == MediaType.DOCUMENT:
            return self.pdf.optimize(source, out_path, aggressive, signals, job)
        
        raise ValueError("Unsupported optimization media type.")
