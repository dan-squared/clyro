import subprocess
import logging
import re
import time
from pathlib import Path
from clyro.core.types import Result
from clyro.errors import ToolExecutionError

logger = logging.getLogger(__name__)

# ── Normal mode: moderate lossy — re-encodes images at good quality, 200 DPI ──
GS_NORMAL_ARGS = [
    "-dAutoFilterGrayImages=false",
    "-dAutoFilterColorImages=false",
    "-dAutoFilterMonoImages=false",
    "-dColorImageFilter=/DCTEncode",
    "-dDownsampleColorImages=true",
    "-dDownsampleGrayImages=true",
    "-dDownsampleMonoImages=true",
    "-dGrayImageFilter=/DCTEncode",
    "-dPassThroughJPEGImages=false",
    "-dPassThroughJPXImages=false",
    "-dShowAcroForm=true",
    "-dColorImageResolution=200",
    "-dGrayImageResolution=200",
    "-dMonoImageResolution=200",
]

# ── Aggressive mode: heavy lossy — lower quality, 150 DPI ──
GS_AGGRESSIVE_ARGS = [
    "-dAutoFilterGrayImages=false",
    "-dAutoFilterColorImages=false",
    "-dAutoFilterMonoImages=true",
    "-dColorImageFilter=/DCTEncode",
    "-dDownsampleColorImages=true",
    "-dDownsampleGrayImages=true",
    "-dDownsampleMonoImages=true",
    "-dGrayImageFilter=/DCTEncode",
    "-dPassThroughJPEGImages=false",
    "-dPassThroughJPXImages=false",
    "-dShowAcroForm=false",
    "-dColorImageResolution=150",
    "-dGrayImageResolution=150",
    "-dMonoImageResolution=150",
]

GS_COMMON_ARGS = [
    "-dALLOWPSTRANSPARENCY",
    "-dAutoRotatePages=/None",
    "-dBATCH",
    "-dCannotEmbedFontPolicy=/Warning",
    "-dColorConversionStrategy=/sRGB",
    "-dColorImageDownsampleThreshold=1.0",
    "-dColorImageDownsampleType=/Bicubic",
    "-dCompressFonts=true",
    "-dCompressPages=true",
    "-dCompressStreams=true",
    "-dConvertCMYKImagesToRGB=true",
    "-dConvertImagesToIndexed=false",
    "-dCreateJobTicket=false",
    "-dDetectDuplicateImages=true",
    "-dDoThumbnails=false",
    "-dEmbedAllFonts=true",
    "-dEncodeColorImages=true",
    "-dEncodeGrayImages=true",
    "-dEncodeMonoImages=true",
    "-dFastWebView=false",
    "-dGrayDetection=true",
    "-dGrayImageDownsampleThreshold=1.0",
    "-dGrayImageDownsampleType=/Bicubic",
    "-dHaveTransparency=true",
    "-dLZWEncodePages=true",
    "-dMaxBitmap=0",
    "-dMonoImageDownsampleThreshold=1.0",
    "-dMonoImageDownsampleType=/Bicubic",
    "-dMonoImageFilter=/CCITTFaxEncode",
    "-dNOPAUSE",
    "-dNOPROMPT",
    "-dOptimize=false",
    "-dParseDSCComments=false",
    "-dParseDSCCommentsForDocInfo=false",
    "-dPDFNOCIDFALLBACK",
    "-dPDFSETTINGS=/ebook",
    "-dPreserveAnnots=true",
    "-dPreserveCopyPage=false",
    "-dPreserveDeviceN=true",
    "-dPreserveEPSInfo=false",
    "-dPreserveHalftoneInfo=false",
    "-dPreserveOPIComments=false",
    "-dPreserveOverprintSettings=true",
    "-dPreserveSeparation=true",
    "-dPrinted=false",
    "-dProcessColorModel=/DeviceRGB",
    "-dSAFER",
    "-dSubsetFonts=true",
    "-dTransferFunctionInfo=/Preserve",
    "-dUCRandBGInfo=/Remove",
]

def _gs_pre_args(qfactor: float) -> list[str]:
    """Build GS pre-args with dynamic QFactor for image quality control."""
    q = f"{qfactor:.2f}"
    return [
        "-c",
        f"<< /ColorImageDict << /QFactor {q} /Blend 1 /HSamples [2 1 1 2] /VSamples [2 1 1 2] >> >> setdistillerparams "
        f"<< /ColorACSImageDict << /QFactor {q} /Blend 1 /HSamples [2 1 1 2] /VSamples [2 1 1 2] >> >> setdistillerparams "
        f"<< /GrayImageDict << /QFactor {q} /Blend 1 /HSamples [2 1 1 2] /VSamples [2 1 1 2] >> >> setdistillerparams "
        f"<< /GrayACSImageDict << /QFactor {q} /Blend 1 /HSamples [2 1 1 2] /VSamples [2 1 1 2] >> >> setdistillerparams "
        "<< /AlwaysEmbed [ ] >> setdistillerparams "
        "<< /NeverEmbed [/Courier /Courier-Bold /Courier-Oblique /Courier-BoldOblique /Helvetica /Helvetica-Bold /Helvetica-Oblique /Helvetica-BoldOblique /Times-Roman /Times-Bold /Times-Italic /Times-BoldItalic /Symbol /ZapfDingbats /Arial] >> setdistillerparams",
        "-f",
        "-c",
        "/originalpdfmark { //pdfmark } bind def /pdfmark { { { counttomark pop } stopped { /pdfmark errordict /unmatchedmark get exec stop } if dup type /nametype ne { /pdfmark errordict /typecheck get exec stop } if dup /DOCINFO eq { (Skipping DOCINFO pdfmark\\\\n) print cleartomark exit } if originalpdfmark exit } loop } def",
        "-f",
    ]

GS_POST_ARGS = [
    "-c", "/pdfmark { originalpdfmark } bind def", "-f",
    "-c", "[ /Producer () /ModDate () /CreationDate () /DOCINFO pdfmark", "-f",
]

class PdfHandler:
    def __init__(self, settings, tools):
        self.settings = settings
        self.tools = tools

    def optimize(self, source: Path, out_path: Path, aggressive: bool, signals, job: 'Job') -> Result:
        signals.progress.emit(job.id, (0, "Starting..."))
        orig_size = source.stat().st_size
        
        # Get total pages
        total_pages = self._get_page_count(source)
        
        is_aggressive = aggressive or self.settings.pdf_compression == "extreme"
        
        cmd = [str(self.tools.ghostscript)]
        cmd.extend(GS_COMMON_ARGS)
        
        if is_aggressive:
            cmd.extend(GS_AGGRESSIVE_ARGS)
            qfactor = 0.76  # Lower quality, smaller files
        else:
            cmd.extend(GS_NORMAL_ARGS)
            qfactor = 0.40  # Good quality, moderate savings

        cmd.extend([
            "-sDEVICE=pdfwrite",
            "-o", str(out_path),
        ])
        
        # Add system fonts if possible (Windows common paths)
        font_paths = [
            Path("C:/Windows/Fonts"),
            Path(Path.home() / "AppData/Local/Microsoft/Windows/Fonts"),
        ]
        available_fonts = [str(p) for p in font_paths if p.exists()]
        if available_fonts:
            cmd.append(f"-sFONTPATH={';'.join(available_fonts)}")

        cmd.extend(_gs_pre_args(qfactor))
        cmd.append(str(source))
        cmd.extend(GS_POST_ARGS)

        
        page_regex = re.compile(r"Page\s+(\d+)")
        
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=subprocess.CREATE_NO_WINDOW, bufsize=1, universal_newlines=True)
            
            while True:
                if job.is_cancelled:
                    process.kill()
                    process.wait()
                    out_path.unlink(missing_ok=True)
                    return None
                
                line = process.stdout.readline()
                if not line:
                    if process.poll() is not None:
                        break
                    time.sleep(0.01)
                    continue

                match = page_regex.search(line)
                if match and total_pages > 0:
                    current_page = int(match.group(1))
                    pct = min(100.0, (current_page / total_pages) * 100.0)
                    signals.progress.emit(job.id, (pct, f"Page {current_page} / {total_pages}"))
                    
            process.wait()
            if process.returncode != 0:
                raise ToolExecutionError("Ghostscript PDF optimization failed.")
                
        except ToolExecutionError:
            raise  # pass through as-is without re-wrapping
        except Exception as e:
            logger.error(f"Ghostscript unexpected error: {e}")
            raise ToolExecutionError(f"Ghostscript failed: {e}")
            
        opt_size = out_path.stat().st_size
        if opt_size >= orig_size and self.settings.skip_if_larger and out_path != source:
            out_path.unlink(missing_ok=True)
            return Result(source, source, orig_size, orig_size)
            
        signals.progress.emit(job.id, (100.0, "Complete"))
        return Result(source, out_path, orig_size, opt_size)

    def _get_page_count(self, source: Path) -> int:
        try:
            import fitz
            doc = fitz.open(source)
            count = doc.page_count
            doc.close()
            return count
        except Exception:
            return 0

class PdfToImageHandler:
    def __init__(self, tools):
        self.tools = tools
        
    def convert(self, source: Path, target_format: str, out_path: Path, signals, job: 'Job') -> Result:
        signals.progress.emit(job.id, 0.1)
        orig_size = source.stat().st_size
        
        try:
            import fitz
            doc = fitz.open(source)
            if doc.page_count > 0:
                # Save just the first page to the out_path directly
                page = doc.load_page(0)
                if job.is_cancelled:
                    doc.close()
                    out_path.unlink(missing_ok=True)
                    return None
                pix = page.get_pixmap(dpi=150)
                pix.save(str(out_path))
                # Render the first page as a preview. (Complex multi-page extraction to ZIP is omitted for simplicity)
            doc.close()
        except Exception as e:
            raise ToolExecutionError(f"PyMuPDF failed to convert PDF to image: {e}")
            
        signals.progress.emit(job.id, (100, "Done"))
        return Result(source, out_path, orig_size, out_path.stat().st_size)

class PdfToWordHandler:
    def __init__(self, tools):
        self.tools = tools
        
    def convert(self, source: Path, target_format: str, out_path: Path, signals, job: 'Job') -> Result:
        signals.progress.emit(job.id, (10.0, "Initializing..."))
        orig_size = source.stat().st_size
        
        try:
            from pdf2docx import Converter
        except ImportError:
            Converter = None

        if not Converter:
            raise ToolExecutionError("pdf2docx library not available.")
            
        # Subclass pdf2docx.Converter to intercept and emit progress to the UI
        class ProgressConverter(Converter):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._current_progress = 10.0
                
            def parse_pages(self, **kwargs):
                signals.progress.emit(job.id, (20.0, "Analyzing Document..."))
                pages = [page for page in self._pages if not page.skip_parsing]
                num_pages = len(pages)
                
                for i, page in enumerate(pages, start=1):
                    if job.is_cancelled:
                        return self # or handle abort

                    # Reserve 20% to 70% for parsing pages
                    pct = 20.0 + (50.0 * (i / max(1, num_pages)))
                    signals.progress.emit(job.id, (pct, f"Parsing page {i} of {num_pages}..."))
                    
                    try:
                        page.parse(**kwargs)
                    except Exception as e:
                        if kwargs.get('raw_exceptions'):
                            raise
                        if not kwargs.get('debug') and kwargs.get('ignore_page_error'):
                            pass
                        else:
                            from pdf2docx.converter import ConversionException
                            raise ConversionException(f'Error when parsing page {page.id + 1}: {e}')
                return self

            def make_docx(self, docx_filename=None, **kwargs):
                if job.is_cancelled: return
                signals.progress.emit(job.id, (75.0, "Generating Word Document..."))
                res = super().make_docx(docx_filename, **kwargs)
                signals.progress.emit(job.id, (95.0, "Finalizing..."))
                return res

        try:
            if job.is_cancelled:
                out_path.unlink(missing_ok=True)
                return None
            signals.progress.emit(job.id, (15.0, "Opening PDF..."))
            cv = ProgressConverter(str(source))
            if job.is_cancelled: 
                cv.close()
                out_path.unlink(missing_ok=True)
                return None
            # The convert method calls parse() then make_docx()
            cv.convert(str(out_path), start=0, end=None)
            cv.close()
        except Exception as e:
            raise ToolExecutionError(f"pdf2docx failed: {e}")
            
        signals.progress.emit(job.id, (100.0, "Complete"))
        return Result(source, out_path, orig_size, out_path.stat().st_size)
