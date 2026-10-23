import sys, os, shutil, subprocess, tempfile, json
from pathlib import Path
from PIL import Image, ImageOps
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QComboBox, QFrame, QListWidget, QListWidgetItem,
    QMessageBox, QProgressBar, QLineEdit, QTabWidget, QTextEdit
)

APP_NAME = "DLab File Converter"
IMAGE_EXTS = {
    ".png",".jpg",".jpeg",".webp",".bmp",".tiff",".tif",".gif",".ico",".avif",
    ".heic",".heif",".jfif",".ppm",".pgm",".pbm",".pnm",".tga",".pcx",".dds",
    ".jp2",".j2k",".psd",".eps"
}
TEXT_EXTS = {".txt",".md",".csv",".html",".htm",".xml",".json",".log",".yaml",".yml",".ini",".rtf"}
OFFICE_EXTS = {
    ".doc",".docx",".docm",".dot",".dotx",".odt",".ott",".rtf",
    ".xls",".xlsx",".xlsm",".ods",".ots",".csv",
    ".ppt",".pptx",".pptm",".odp",".otp",".odg",".odf",
    ".html",".htm",".txt"
}
MEDIA_EXTS = {
    ".mp4",".mov",".mkv",".avi",".webm",".mp3",".wav",".aac",".flac",".ogg",
    ".m4a",".wma",".mpeg",".mpg",".3gp",".wmv",".flv",".ts",".opus",".aiff",
    ".amr",".m4v",".m2ts",".mts",".vob",".ogv",".mp2",".ac3",".alac",".caf",
    ".mid",".midi",".mxf",".dv",".f4v",".mka",".m4b",".ape",".wv",".tta",
    ".m2v",".mpe",".y4m",".nut",".rm",".rmvb",".asf",".fla",".flic",
    ".srt",".vtt",".ass",".ssa",".sub",".smi"
}
ARCHIVE_EXTS = {".zip",".7z",".rar",".tar",".gz",".bz2",".xz",".tgz"}
EBOOK_EXTS = {".epub",".mobi",".azw",".azw3",".fb2",".lit",".lrf",".pdb",".cbz",".cbr",".djvu"}
ALL_IMAGE_OUT = [".png",".jpg",".webp",".bmp",".tiff",".gif",".ico",".avif",".pdf"]
ALL_DOC_OUT = [".pdf",".txt",".docx",".odt",".rtf",".xlsx",".ods",".pptx",".odp",".html",".md",".csv"]
ALL_MEDIA_OUT = sorted(MEDIA_EXTS)
EBOOK_OUT = [".epub",".mobi",".azw3",".fb2",".pdf",".txt",".docx",".html",".rtf"]

def find_tool(*names):
    for name in names:
        p = shutil.which(name)
        if p:
            return p
    return None

def normalize_heic():
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except Exception:
        pass

def image_convert(src, dst, ext):
    normalize_heic()
    with Image.open(src) as opened:
        im = ImageOps.exif_transpose(opened)
        if ext == ".pdf":
            im.convert("RGB").save(dst, "PDF", resolution=150)
        elif ext in (".jpg", ".jpeg", ".jfif"):
            if im.mode in ("RGBA", "LA", "P"):
                rgba = im.convert("RGBA")
                bg = Image.new("RGB", rgba.size, "white")
                bg.paste(rgba, mask=rgba.getchannel("A"))
                im = bg
            else:
                im = im.convert("RGB")
            im.save(dst, "JPEG", quality=93, optimize=True)
        elif ext == ".ico":
            im.save(dst, format="ICO", sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
        elif ext == ".avif":
            im.save(dst, format="AVIF", quality=90)
        elif ext == ".gif":
            im.save(dst, save_all=True)
        elif ext in (".tif", ".tiff"):
            im.save(dst, format="TIFF")
        elif ext == ".jp2":
            im.save(dst, format="JPEG2000")
        elif ext == ".eps":
            im.convert("RGB").save(dst, format="EPS")
        else:
            im.save(dst)

def svg_convert(src, dst, ext):
    try:
        import cairosvg
    except ImportError:
        raise RuntimeError("Per SVG serve CairoSVG: installa cairosvg. In alternativa usa Inkscape.")
    if ext == ".pdf":
        cairosvg.svg2pdf(url=str(src), write_to=str(dst))
    elif ext in (".png", ".jpg", ".jpeg"):
        tmp = dst if ext == ".png" else dst.with_suffix(".png")
        cairosvg.svg2png(url=str(src), write_to=str(tmp))
        if ext != ".png":
            with Image.open(tmp) as im:
                im.convert("RGB").save(dst, "JPEG", quality=93)
            tmp.unlink(missing_ok=True)
    else:
        raise RuntimeError("SVG supportato come input verso PNG, JPG o PDF.")

def pdf_to_text(src, dst):
    reader = PdfReader(str(src))
    with open(dst, "w", encoding="utf-8") as f:
        for i, page in enumerate(reader.pages, 1):
            f.write(f"--- Pagina {i} ---\n")
            f.write(page.extract_text() or "[Nessun testo estraibile: possibile PDF scansionato; OCR non incluso]\n")
            f.write("\n\n")

def text_to_pdf(src, dst):
    text = Path(src).read_text(encoding="utf-8", errors="replace")
    c = canvas.Canvas(str(dst), pagesize=(595,842))
    margin, y = 48, 794
    c.setFont("Helvetica", 10)
    for paragraph in text.splitlines() or [""]:
        words, line = paragraph.split(), ""
        for word in words:
            candidate = (line + " " + word).strip()
            if c.stringWidth(candidate, "Helvetica", 10) > 499:
                c.drawString(margin,y,line); y-=14; line=word
            else:
                line=candidate
        c.drawString(margin,y,line); y-=14
        if y < 48:
            c.showPage(); c.setFont("Helvetica",10); y=794
    c.save()

def office_convert(src, outdir, ext):
    lo = find_tool("libreoffice", "soffice")
    if not lo:
        raise RuntimeError("Per documenti Office/PDF serve LibreOffice installato.")
    proc = subprocess.run([lo, "--headless", "--convert-to", ext.lstrip("."), "--outdir", str(outdir), str(src)],
                          capture_output=True, text=True, timeout=300)
    expected = outdir / (src.stem + ext)
    if proc.returncode or not expected.exists():
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError("LibreOffice non ha completato la conversione: formato non supportato o file non valido. " + detail[-300:])
    return expected

def ebook_convert(src, dst):
    tool = find_tool("ebook-convert")
    if not tool:
        raise RuntimeError("Per ebook serve Calibre installato (comando ebook-convert).")
    proc = subprocess.run([tool, str(src), str(dst)], capture_output=True, text=True, timeout=600)
    if proc.returncode or not dst.exists():
        raise RuntimeError("Calibre non ha completato la conversione. DRM, file danneggiato o formato non supportato.")
    return dst

def media_convert(src, dst):
    ffmpeg = find_tool("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("Per audio/video/sottotitoli serve FFmpeg installato e disponibile nel PATH.")
    proc = subprocess.run([ffmpeg, "-hide_banner", "-y", "-i", str(src), "-map_metadata", "0", str(dst)],
                          capture_output=True, text=True, timeout=1800)
    if proc.returncode or not dst.exists():
        raise RuntimeError("FFmpeg non ha completato la conversione. Potrebbe esserci un codec o una coppia di formati incompatibile.")

def archive_convert(src, dst, ext):
    seven = find_tool("7z", "7zz", "7za")
    if not seven:
        raise RuntimeError("Per gli archivi serve 7-Zip installato e disponibile nel PATH.")
    with tempfile.TemporaryDirectory(prefix="dlab_archive_") as td:
        root = Path(td)
        extract = root / "contents"
        extract.mkdir()
        proc = subprocess.run([seven, "x", "-y", f"-o{extract}", str(src)], capture_output=True, text=True, timeout=600)
        if proc.returncode:
            raise RuntimeError("Estrazione non riuscita: archivio protetto da password, danneggiato o formato non supportato.")
        if ext == ".zip":
            shutil.make_archive(str(dst.with_suffix("")), "zip", root_dir=extract)
            return dst
        fmt = {"tgz":"gzip", "gz":"gzip", "bz2":"bzip2", "xz":"xz"}.get(ext.lstrip("."), ext.lstrip("."))
        # Pass all extracted paths explicitly; do not rely on shell wildcard expansion.
        entries = [str(p) for p in extract.iterdir()]
        if not entries:
            raise RuntimeError("L'archivio è vuoto.")
        proc2 = subprocess.run([seven, "a", "-t"+fmt, str(dst), *entries], capture_output=True, text=True, timeout=600)
        if proc2.returncode or not dst.exists():
            raise RuntimeError("7-Zip non ha creato il formato richiesto. Alcuni formati compressi richiedono un archivio TAR intermedio.")
    return dst

def convert_one(src, outdir, ext):
    src = Path(src); outdir = Path(outdir)
    src_ext = src.suffix.lower()
    normalize_heic()
    dst = outdir / (src.stem + ext)
    if src_ext in IMAGE_EXTS and (ext in set(ALL_IMAGE_OUT) | {".jpeg", ".jfif", ".jp2", ".eps"}):
        image_convert(src, dst, ext)
    elif src_ext == ".svg" and ext in {".png",".jpg",".jpeg",".pdf"}:
        svg_convert(src, dst, ext)
    elif src_ext == ".pdf" and ext == ".txt":
        pdf_to_text(src, dst)
    elif src_ext in TEXT_EXTS and ext == ".pdf":
        text_to_pdf(src, dst)
    elif src_ext in OFFICE_EXTS and (ext in OFFICE_EXTS or ext == ".pdf"):
        return office_convert(src, outdir, ext)
    elif src_ext in EBOOK_EXTS and ext in EBOOK_OUT:
        return ebook_convert(src, dst)
    elif src_ext in MEDIA_EXTS and ext in MEDIA_EXTS:
        media_convert(src, dst)
    elif src_ext in ARCHIVE_EXTS and ext in {".zip", ".7z", ".tar", ".gz", ".bz2", ".xz", ".tgz"}:
        return archive_convert(src, dst, ext)
    else:
        raise RuntimeError(f"Conversione {src_ext} → {ext} non implementata/supportata. Verifica la scheda Formati e requisiti.")
    if not dst.exists() or dst.stat().st_size == 0:
        raise RuntimeError("Il file di destinazione non è stato creato correttamente.")
    return dst

class Worker(QThread):
    progress = Signal(int, str)
    done = Signal(list, list)
    def __init__(self, files, ext, target):
        super().__init__(); self.files=files; self.ext=ext; self.target=Path(target)
    def run(self):
        good,bad=[],[]
        self.target.mkdir(parents=True,exist_ok=True)
        for i,name in enumerate(self.files,1):
            try: good.append(str(convert_one(name,self.target,self.ext)))
            except Exception as e: bad.append(f"{Path(name).name}: {e}")
            self.progress.emit(int(i*100/len(self.files)),f"Elaborati {i} di {len(self.files)}")
        self.done.emit(good,bad)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("DLab File Converter"); self.resize(1160,790); self.setAcceptDrops(True); self.files=[]
        self.setStyleSheet("""
        QWidget{background:#f4f6f8;color:#263238;font-family:'Segoe UI';font-size:14px}
        QFrame#panel,QGroupBox{background:white;border:1px solid #e0e5e9;border-radius:14px}
        QLabel#brand{font-size:25px;font-weight:850;background:transparent}
        QLabel#muted{color:#6c7780;background:transparent}
        QPushButton{background:#263238;color:white;border:0;border-radius:9px;padding:11px 14px;font-weight:650}
        QPushButton:hover{background:#405057}
        QPushButton#secondary{background:white;color:#263238;border:1px solid #d7dde2}
        QPushButton#accent{background:#f4c542;color:#263238}
        QComboBox,QLineEdit{background:white;border:1px solid #d7dde2;border-radius:8px;padding:9px}
        QListWidget{background:#fbfcfd;border:1px dashed #c8d0d7;border-radius:10px;padding:8px}
        QProgressBar{background:#e7ebef;border:0;border-radius:6px;height:12px}
        QProgressBar::chunk{background:#b87333;border-radius:6px}
        """)
        c=QWidget(); self.setCentralWidget(c); outer=QVBoxLayout(c); outer.setContentsMargins(26,22,26,20); outer.setSpacing(15)
        top=QHBoxLayout(); brand=QLabel("DLab"); brand.setObjectName("brand"); brand.setStyleSheet("color:#263238")
        name=QLabel("File Converter"); name.setObjectName("brand"); name.setStyleSheet("color:#b87333")
        lefttop=QVBoxLayout(); line=QHBoxLayout(); line.addWidget(brand); line.addWidget(name); line.addStretch(); lefttop.addLayout(line)
        tag=QLabel("DESKTOP WINDOWS · CONVERSIONI IN LOCALE"); tag.setObjectName("muted"); lefttop.addWidget(tag); top.addLayout(lefttop); top.addStretch()
        badge=QLabel("PORTABLE · V3"); badge.setStyleSheet("background:#fff0c2;padding:8px 12px;border-radius:8px;font-size:11px;font-weight:800"); top.addWidget(badge); outer.addLayout(top)
        heading=QLabel("Un unico strumento per convertire i tuoi file"); heading.setStyleSheet("font-size:26px;font-weight:800;background:transparent"); outer.addWidget(heading)
        desc=QLabel("Aggiungi file singoli o multipli, scegli la famiglia di conversione e salva i risultati in locale."); desc.setObjectName("muted"); outer.addWidget(desc)
        row=QHBoxLayout(); row.setSpacing(16); outer.addLayout(row,1)
        panel=QFrame(); panel.setObjectName("panel"); pl=QVBoxLayout(panel); pl.setContentsMargins(18,18,18,18); row.addWidget(panel,3)
        label=QLabel("01  ·  File da convertire"); label.setStyleSheet("font-size:16px;font-weight:800;background:transparent"); pl.addWidget(label)
        self.list=QListWidget(); self.list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection); self.list.setMinimumHeight(250); pl.addWidget(self.list,1)
        btns=QHBoxLayout()
        for txt,fn in [("＋ Aggiungi file",self.add_files),("Rimuovi selezionati",self.remove_selected),("Svuota",self.clear_files)]:
            b=QPushButton(txt); b.setObjectName("secondary"); b.clicked.connect(fn); btns.addWidget(b)
        pl.addLayout(btns); self.count=QLabel("0 file · Trascina qui i file per aggiungerli"); self.count.setObjectName("muted"); pl.addWidget(self.count)
        side=QFrame(); side.setObjectName("panel"); sl=QVBoxLayout(side); sl.setContentsMargins(18,18,18,18); row.addWidget(side,2)
        t=QLabel("02  ·  Conversione"); t.setStyleSheet("font-size:16px;font-weight:800;background:transparent"); sl.addWidget(t)
        sl.addWidget(QLabel("Categoria")); self.cat=QComboBox(); self.cat.addItems(["Immagini","Documenti e PDF","Audio, video e sottotitoli","Archivi","E-book"]); self.cat.currentTextChanged.connect(self.update_formats); sl.addWidget(self.cat)
        sl.addWidget(QLabel("Formato di destinazione")); self.fmt=QComboBox(); sl.addWidget(self.fmt)
        sl.addWidget(QLabel("Cartella di destinazione")); h=QHBoxLayout(); self.out=QLineEdit(str(Path.home()/"Downloads"/"DLab Convertiti")); h.addWidget(self.out)
        browse=QPushButton("Sfoglia"); browse.setObjectName("secondary"); browse.clicked.connect(self.pick_dir); h.addWidget(browse); sl.addLayout(h)
        self.progress=QProgressBar(); self.progress.setValue(0); sl.addWidget(self.progress)
        self.status=QLabel("Pronto"); self.status.setObjectName("muted"); self.status.setWordWrap(True); sl.addWidget(self.status)
        go=QPushButton("Converti e salva"); go.setObjectName("accent"); go.clicked.connect(self.start); sl.addWidget(go)
        sl.addStretch()
        self.tabs=QTabWidget(); self.tabs.setMinimumHeight(190); outer.addWidget(self.tabs)
        supported=QTextEdit(); supported.setReadOnly(True); supported.setPlainText(
            "IMMAGINI RASTER: HEIC/HEIF, AVIF, JPG/JPEG/JFIF, PNG, WebP, BMP, TIFF, GIF, ICO, PPM/PGM/PBM/PNM, TGA, PCX, DDS, JPEG 2000, PSD (lettura limitata), EPS (lettura/scrittura limitata). Destinazioni: PNG, JPG, WebP, BMP, TIFF, GIF, ICO, AVIF, PDF, JPEG 2000, EPS se supportati dalla build Pillow. HEIC è soprattutto un formato di input.\n\n"
            "VETTORIALI: SVG → PNG/JPG/PDF tramite CairoSVG (da installare separatamente). DXF/DWG non inclusi direttamente: richiedono un convertitore CAD dedicato.\n\n"
            "PDF/TESTO: PDF → TXT (testo incorporato); TXT/MD/CSV/HTML/XML/JSON/LOG/YAML/INI/RTF → PDF quando applicabile. PDF scansionati richiedono OCR esterno. Il programma non converte PDF in Word in modo nativo: usare LibreOffice o uno strumento dedicato.\n\n"
            "OFFICE: DOC/DOCX/DOCM/DOT, ODT/OTT/RTF, XLS/XLSX/XLSM/ODS/CSV, PPT/PPTX/PPTM/ODP/ODG e altri formati gestiti da LibreOffice. Conversione tramite LibreOffice installato; le combinazioni disponibili dipendono dai filtri di importazione/esportazione.\n\n"
            "AUDIO/VIDEO/SOTTOTITOLI: MP4, MOV, MKV, AVI, WebM, MP3, WAV, AAC, FLAC, OGG, M4A, WMA, MPEG, 3GP, WMV, FLV, TS, OPUS, AIFF, AMR, M4V, M2TS, VOB, MXF, ASF, RM/RMVB, APE, WV, CAF, MIDI e SRT/VTT/ASS/SSA/SUB/SMI. Richiede FFmpeg; non tutte le coppie sono compatibili e i sottotitoli non si convertono come normali tracce audio/video.\n\n"
            "ARCHIVI: ZIP, 7Z, RAR in lettura quando supportato da 7-Zip, TAR, GZ, BZ2, XZ, TGZ. Richiede 7-Zip. Alcuni formati compressi, archivi annidati, cifrati o danneggiati possono fallire.\n\n"
            "E-BOOK: EPUB, MOBI, AZW/AZW3, FB2, LIT, LRF, PDB, CBZ/CBR, DJVU come sorgenti quando supportate da Calibre; destinazioni EPUB/MOBI/AZW3/FB2/PDF/TXT/DOCX/HTML/RTF. Richiede Calibre. DRM e alcuni formati fumetto/scansione possono impedire la conversione.\n\n"
            "FORMATI NON UNIVERSALI: CAD (DWG/DXF), 3D (STL/OBJ/FBX/GLB), database, font, file eseguibili e formati proprietari richiedono strumenti specifici e non sono inclusi in questa versione. Nessun convertitore può garantire ogni coppia di formati.")
        self.tabs.addTab(supported,"Formati e compatibilità")
        deps=QTextEdit(); deps.setReadOnly(True); deps.setPlainText(
            "Elaborazione locale: i file non vengono caricati su un servizio online e gli originali non vengono modificati.\n\n"
            "Inclusi nella build Python: Pillow, pillow-heif, pypdf, reportlab, PySide6.\n"
            "Per Office/PDF avanzati: installare LibreOffice.\n"
            "Per audio/video/sottotitoli: installare FFmpeg e aggiungerlo al PATH.\n"
            "Per archivi: installare 7-Zip e aggiungerlo al PATH.\n"
            "Per e-book: installare Calibre (ebook-convert nel PATH).\n"
            "Per SVG: installare CairoSVG con pip oppure usare Inkscape; in questa versione è previsto il modulo CairoSVG.\n\n"
            "L'EXE portatile non incorpora automaticamente LibreOffice, FFmpeg, 7-Zip, Calibre o CairoSVG. La build deve essere testata su Windows reale.")
        self.tabs.addTab(deps,"Dipendenze e limiti")
        foot=QLabel("DLab · File originali intatti · Elaborazione locale"); foot.setObjectName("muted"); foot.setAlignment(Qt.AlignmentFlag.AlignCenter); outer.addWidget(foot)
        self.update_formats(self.cat.currentText())
    def add_files(self):
        files,_=QFileDialog.getOpenFileNames(self,"Seleziona file")
        self.add_paths(files)
    def add_paths(self,paths):
        for p in paths:
            if p and p not in self.files and Path(p).is_file():
                self.files.append(p); self.list.addItem(QListWidgetItem(f"{Path(p).name}   ·   {Path(p).suffix.lower()}"))
        self.count.setText(f"{len(self.files)} file selezionati")
    def remove_selected(self):
        for i in sorted([self.list.row(x) for x in self.list.selectedItems()],reverse=True):
            self.list.takeItem(i); self.files.pop(i)
        self.count.setText(f"{len(self.files)} file selezionati")
    def clear_files(self):
        self.files=[]; self.list.clear(); self.count.setText("0 file selezionati")
    def pick_dir(self):
        d=QFileDialog.getExistingDirectory(self,"Cartella di destinazione",self.out.text())
        if d:self.out.setText(d)
    def update_formats(self,cat):
        self.fmt.clear()
        opts={
            "Immagini":[("PNG",".png"),("JPG/JPEG",".jpg"),("WebP",".webp"),("BMP",".bmp"),("TIFF",".tiff"),("GIF",".gif"),("ICO",".ico"),("AVIF",".avif"),("JPEG 2000",".jp2"),("EPS",".eps"),("PDF da immagine",".pdf")],
            "Documenti e PDF":[(x.upper(),x) for x in [".pdf",".txt",".docx",".doc",".odt",".rtf",".xlsx",".xls",".ods",".pptx",".ppt",".odp",".html",".md",".csv"]],
            "Audio, video e sottotitoli":[(x.upper(),x) for x in sorted(MEDIA_EXTS)],
            "Archivi":[(x.upper(),x) for x in [".zip",".7z",".tar",".gz",".bz2",".xz",".tgz"]],
            "E-book":[(x.upper(),x) for x in EBOOK_OUT]
        }
        for label,ext in opts.get(cat,[]):self.fmt.addItem(label,ext)
    def start(self):
        if not self.files:
            QMessageBox.warning(self,"Nessun file","Aggiungi almeno un file.");return
        if not self.fmt.currentData():
            QMessageBox.warning(self,"Formato mancante","Scegli un formato di destinazione.");return
        self.progress.setValue(0); self.status.setText("Conversione in corso…")
        self.worker=Worker(list(self.files),self.fmt.currentData(),self.out.text())
        self.worker.progress.connect(lambda v,m:(self.progress.setValue(v),self.status.setText(m)))
        self.worker.done.connect(self.finish); self.worker.start()
    def finish(self,good,bad):
        self.status.setText(f"Completati: {len(good)} · Errori: {len(bad)}")
        msg=f"Conversioni riuscite: {len(good)}\nConversioni non riuscite: {len(bad)}"
        if bad: msg += "\n\n" + "\n".join(bad[:12])
        QMessageBox.information(self,"Risultato conversione",msg)
    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
    def dropEvent(self,event):
        self.add_paths([u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()])

def main():
    app=QApplication(sys.argv)
    w=MainWindow(); w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
