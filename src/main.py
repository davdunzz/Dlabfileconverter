import sys
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageOps
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QComboBox, QListWidget,
    QProgressBar, QMessageBox, QLineEdit, QFrame
)

APP_NAME = "DLab File Converter"

def register_heic():
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except Exception:
        pass

def find_program(*names):
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    return None

def convert_file(source, destination_folder, target_ext):
    source = Path(source)
    destination_folder = Path(destination_folder)
    destination_folder.mkdir(parents=True, exist_ok=True)
    target = destination_folder / f"{source.stem}{target_ext}"
    source_ext = source.suffix.lower()

    # Images
    register_heic()
    image_inputs = {
        ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff",
        ".gif", ".ico", ".heic", ".heif", ".avif"
    }
    image_outputs = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif", ".ico"}
    if source_ext in image_inputs and target_ext in image_outputs:
        with Image.open(source) as original:
            image = ImageOps.exif_transpose(original)
            if target_ext in {".jpg", ".jpeg"}:
                if image.mode in ("RGBA", "LA", "P"):
                    rgba = image.convert("RGBA")
                    background = Image.new("RGB", rgba.size, "white")
                    background.paste(rgba, mask=rgba.getchannel("A"))
                    image = background
                else:
                    image = image.convert("RGB")
                image.save(target, "JPEG", quality=92, optimize=True)
            elif target_ext == ".ico":
                image.save(target, format="ICO", sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
            elif target_ext in {".tif", ".tiff"}:
                image.save(target, format="TIFF")
            else:
                image.save(target)
        return target

    # Text files to PDF
    text_inputs = {".txt", ".md", ".csv", ".log"}
    if source_ext in text_inputs and target_ext == ".pdf":
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        text = source.read_text(encoding="utf-8", errors="replace")
        pdf = canvas.Canvas(str(target), pagesize=A4)
        width, height = A4
        left, y = 42, height - 42
        pdf.setFont("Helvetica", 9)
        for paragraph in text.splitlines() or [""]:
            words, line = paragraph.split(), ""
            for word in words:
                candidate = (line + " " + word).strip()
                if pdf.stringWidth(candidate, "Helvetica", 9) > width - 84:
                    pdf.drawString(left, y, line)
                    y -= 12
                    line = word
                else:
                    line = candidate
            pdf.drawString(left, y, line)
            y -= 12
            if y < 42:
                pdf.showPage()
                pdf.setFont("Helvetica", 9)
                y = height - 42
        pdf.save()
        return target

    # PDF to TXT (text layer only; no OCR)
    if source_ext == ".pdf" and target_ext == ".txt":
        from pypdf import PdfReader
        reader = PdfReader(str(source))
        with target.open("w", encoding="utf-8") as output:
            for page_number, page in enumerate(reader.pages, start=1):
                output.write(f"--- Pagina {page_number} ---\n")
                output.write(page.extract_text() or "[Nessun testo estraibile; possibile PDF scansionato]\n")
                output.write("\n")
        return target

    # Office documents via LibreOffice
    office_inputs = {
        ".doc", ".docx", ".odt", ".rtf", ".xls", ".xlsx", ".ods",
        ".ppt", ".pptx", ".odp", ".html", ".htm", ".csv", ".txt"
    }
    office_outputs = {".pdf", ".docx", ".odt", ".rtf", ".xlsx", ".ods", ".pptx", ".odp", ".html", ".txt", ".csv"}
    if source_ext in office_inputs and target_ext in office_outputs:
        libreoffice = find_program("libreoffice", "soffice")
        if not libreoffice:
            raise RuntimeError("Per questa conversione installa LibreOffice e rendilo disponibile nel PATH.")
        result = subprocess.run(
            [libreoffice, "--headless", "--convert-to", target_ext.lstrip("."), "--outdir", str(destination_folder), str(source)],
            capture_output=True, text=True, timeout=180
        )
        if result.returncode != 0 or not target.exists():
            raise RuntimeError("LibreOffice non ha completato la conversione. Verifica il file e il formato richiesto.")
        return target

    # Audio/video via FFmpeg
    media_exts = {
        ".mp4", ".mov", ".mkv", ".avi", ".webm", ".mp3", ".wav", ".aac",
        ".flac", ".ogg", ".m4a", ".wma", ".mpeg", ".mpg", ".3gp", ".wmv",
        ".flv", ".ts", ".opus", ".aiff", ".m4v", ".m2ts", ".mts", ".vob"
    }
    if source_ext in media_exts and target_ext in media_exts:
        ffmpeg = find_program("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("Per audio/video installa FFmpeg e aggiungilo al PATH.")
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-y", "-i", str(source), str(target)],
            capture_output=True, text=True, timeout=900
        )
        if result.returncode != 0 or not target.exists():
            raise RuntimeError("FFmpeg non ha completato la conversione: codec o coppia di formati non compatibile.")
        return target

    raise RuntimeError(
        f"Conversione {source_ext or '(senza estensione)'} → {target_ext} non supportata. "
        "Questa versione privilegia le conversioni più comuni e affidabili."
    )

class ConversionWorker(QThread):
    progress = Signal(int, str)
    finished_result = Signal(list, list)

    def __init__(self, files, extension, destination):
        super().__init__()
        self.files = files
        self.extension = extension
        self.destination = destination

    def run(self):
        successes, errors = [], []
        for index, file_path in enumerate(self.files, start=1):
            try:
                output = convert_file(file_path, self.destination, self.extension)
                successes.append(str(output))
            except Exception as error:
                errors.append(f"{Path(file_path).name}: {error}")
            self.progress.emit(int(index * 100 / len(self.files)), f"Elaborati {index}/{len(self.files)}")
        self.finished_result.emit(successes, errors)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(820, 620)
        self.files = []
        self.setStyleSheet("""
            QWidget { background:#f4f6f8; color:#263238; font-family:'Segoe UI'; font-size:14px; }
            QFrame { background:white; border:1px solid #dfe4e8; border-radius:12px; }
            QLabel#title { font-size:25px; font-weight:800; background:transparent; }
            QLabel#sub { color:#66727b; background:transparent; }
            QPushButton { background:#263238; color:white; border:0; border-radius:8px; padding:10px 13px; font-weight:600; }
            QPushButton:hover { background:#45545b; }
            QPushButton#accent { background:#f4c542; color:#263238; }
            QPushButton#light { background:white; color:#263238; border:1px solid #d8dee3; }
            QComboBox, QLineEdit { background:white; border:1px solid #d8dee3; border-radius:7px; padding:8px; }
            QListWidget { background:#fbfcfd; border:1px dashed #c8d0d7; border-radius:8px; padding:7px; }
            QProgressBar { background:#e4e9ed; border:0; border-radius:5px; height:12px; }
            QProgressBar::chunk { background:#b87333; border-radius:5px; }
        """)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("DLab File Converter")
        title.setObjectName("title")
        title.setStyleSheet("color:#b87333")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(QLabel("DESKTOP · WINDOWS"))
        layout.addLayout(header)
        subtitle = QLabel("Conversioni essenziali, in locale, senza modificare i file originali.")
        subtitle.setObjectName("sub")
        layout.addWidget(subtitle)

        panel = QFrame()
        body = QVBoxLayout(panel)
        body.setContentsMargins(16, 16, 16, 16)
        body.setSpacing(10)
        layout.addWidget(panel, 1)

        body.addWidget(QLabel("1. Seleziona i file"))
        self.file_list = QListWidget()
        body.addWidget(self.file_list, 1)
        buttons = QHBoxLayout()
        add = QPushButton("Aggiungi file")
        add.clicked.connect(self.add_files)
        remove = QPushButton("Rimuovi selezionati")
        remove.setObjectName("light")
        remove.clicked.connect(self.remove_selected)
        clear = QPushButton("Svuota")
        clear.setObjectName("light")
        clear.clicked.connect(self.clear_files)
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addWidget(clear)
        body.addLayout(buttons)

        body.addWidget(QLabel("2. Scegli il formato di destinazione"))
        self.format_box = QComboBox()
        self.formats = [
            ("Immagine PNG", ".png"), ("Immagine JPG", ".jpg"),
            ("Immagine WebP", ".webp"), ("Immagine BMP", ".bmp"),
            ("Immagine TIFF", ".tiff"), ("Immagine GIF", ".gif"),
            ("Immagine ICO", ".ico"), ("Documento PDF", ".pdf"),
            ("Testo TXT", ".txt"), ("Documento DOCX", ".docx"),
            ("Foglio XLSX", ".xlsx"), ("Presentazione PPTX", ".pptx"),
            ("Audio MP3", ".mp3"), ("Audio WAV", ".wav"),
            ("Audio FLAC", ".flac"), ("Video MP4", ".mp4"),
            ("Video MKV", ".mkv"), ("Video WEBM", ".webm"),
        ]
        for label, extension in self.formats:
            self.format_box.addItem(label, extension)
        body.addWidget(self.format_box)

        body.addWidget(QLabel("3. Cartella di destinazione"))
        destination_row = QHBoxLayout()
        self.destination = QLineEdit(str(Path.home() / "Downloads" / "DLab Convertiti"))
        destination_row.addWidget(self.destination)
        browse = QPushButton("Sfoglia")
        browse.setObjectName("light")
        browse.clicked.connect(self.choose_destination)
        destination_row.addWidget(browse)
        body.addLayout(destination_row)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        body.addWidget(self.progress)
        self.status = QLabel("Pronto")
        self.status.setObjectName("sub")
        body.addWidget(self.status)
        self.convert_button = QPushButton("Converti file")
        self.convert_button.setObjectName("accent")
        self.convert_button.clicked.connect(self.start_conversion)
        body.addWidget(self.convert_button)

        footer = QLabel("Office avanzato richiede LibreOffice · Audio/video richiede FFmpeg · PDF scansionati non includono OCR")
        footer.setObjectName("sub")
        footer.setWordWrap(True)
        layout.addWidget(footer)

    def add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Seleziona i file")
        for path in paths:
            if path not in self.files:
                self.files.append(path)
                self.file_list.addItem(f"{Path(path).name}   ({Path(path).suffix.lower()})")
        self.status.setText(f"{len(self.files)} file selezionati")

    def remove_selected(self):
        selected_rows = sorted([self.file_list.row(item) for item in self.file_list.selectedItems()], reverse=True)
        for row in selected_rows:
            self.file_list.takeItem(row)
            self.files.pop(row)
        self.status.setText(f"{len(self.files)} file selezionati")

    def clear_files(self):
        self.files.clear()
        self.file_list.clear()
        self.status.setText("Nessun file selezionato")

    def choose_destination(self):
        path = QFileDialog.getExistingDirectory(self, "Scegli la cartella", self.destination.text())
        if path:
            self.destination.setText(path)

    def start_conversion(self):
        if not self.files:
            QMessageBox.warning(self, "File mancanti", "Aggiungi almeno un file da convertire.")
            return
        self.convert_button.setEnabled(False)
        self.progress.setValue(0)
        self.worker = ConversionWorker(self.files.copy(), self.format_box.currentData(), self.destination.text())
        self.worker.progress.connect(self.update_progress)
        self.worker.finished_result.connect(self.show_result)
        self.worker.start()

    def update_progress(self, value, message):
        self.progress.setValue(value)
        self.status.setText(message)

    def show_result(self, successes, errors):
        self.convert_button.setEnabled(True)
        summary = f"Conversioni riuscite: {len(successes)}\nErrori: {len(errors)}"
        if errors:
            summary += "\n\n" + "\n".join(errors[:8])
        QMessageBox.information(self, "Conversione terminata", summary)
        self.status.setText(f"Completate {len(successes)} conversioni; errori: {len(errors)}")

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
