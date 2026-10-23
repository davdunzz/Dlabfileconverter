# DLab File Converter — Desktop V3

Applicazione desktop Windows con interfaccia PySide6, elaborazione locale e supporto a conversioni batch.

## Avvio sviluppo
1. Installa Python 3.11 o superiore.
2. Apri la cartella del progetto e lancia `AVVIA_IN_SVILUPPO.bat`, oppure:
   ```bash
   pip install -r requirements.txt
   python src/main.py
   ```

## EXE Windows tramite GitHub
Carica i file nel repository GitHub e avvia il workflow **Build Windows EXE** dalla scheda Actions. Il workflow genera un EXE con PyInstaller come artifact scaricabile. Per creare una release, crea un tag che inizi con `v`, ad esempio `v3.0.0`.

## Famiglie di conversione
- Immagini raster: JPG/JPEG, PNG, WebP, BMP, TIFF, GIF, ICO, AVIF, HEIC/HEIF in ingresso, PPM/PGM/PBM/PNM, TGA, PCX, DDS, JPEG 2000 ed EPS/PSD con limiti dovuti ai codec Pillow.
- SVG: SVG verso PNG/JPG/PDF con CairoSVG opzionale.
- PDF e testo: PDF verso TXT; testi verso PDF.
- Office: formati Word, Excel, PowerPoint e OpenDocument gestiti da LibreOffice.
- Audio, video e sottotitoli: formati gestiti da FFmpeg, inclusi contenitori e codec comuni.
- Archivi: ZIP, 7Z, TAR, GZ, BZ2, XZ, TGZ e RAR in ingresso quando 7-Zip li supporta.
- E-book: EPUB, MOBI, AZW/AZW3, FB2 e altri formati gestiti da Calibre.

## Dipendenze esterne opzionali
- LibreOffice: conversioni Office e documenti avanzate.
- FFmpeg: audio/video e sottotitoli.
- 7-Zip: archivi.
- Calibre: e-book (`ebook-convert` nel PATH).
- CairoSVG: conversioni SVG.

Questi programmi non vengono inclusi automaticamente nell'EXE. Devono essere installati sul PC ed essere accessibili nel PATH, salvo configurazioni personalizzate.

## Limiti importanti
Non esiste una conversione universale per ogni coppia di formati. DRM, file protetti, codec mancanti, PDF scansionati, CAD, 3D, database, font e formati proprietari possono richiedere software dedicato. PDF scansionati richiedono OCR; questa versione non include OCR integrato. La compatibilità concreta dipende dal file e dagli strumenti installati. Testare sempre i risultati prima di usarli in produzione.

## Privacy
I file vengono elaborati localmente; l'app non li carica su un servizio web. Gli originali non vengono modificati.
