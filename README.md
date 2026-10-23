# DLab File Converter — versione essenziale

Applicazione desktop Windows con PySide6. La priorità è una base semplice da avviare e compilare.

## Avvio in sviluppo
- Installa Python 3.11 o superiore.
- Esegui `AVVIA_IN_SVILUPPO.bat`, oppure:
  `python -m pip install -r requirements.txt`
  `python src/main.py`

## Creazione EXE con GitHub Actions
Carica la struttura completa nel ramo `main`. Apri la scheda **Actions**, seleziona **Build Windows portable EXE** e premi **Run workflow**. Il workflow parte anche automaticamente quando modifichi `src/`, `requirements.txt` o il file YAML del workflow. Al termine scarica l'artifact `DLabFileConverter-Windows`.

## Conversioni incluse
- Immagini comuni, con HEIC/HEIF in ingresso.
- TXT/MD/CSV/LOG verso PDF.
- PDF verso TXT (solo testo incorporato; nessun OCR).
- Formati Office tramite LibreOffice installato.
- Audio/video tramite FFmpeg installato.

Non tutte le coppie di formati sono compatibili. LibreOffice e FFmpeg non sono inclusi nell'EXE e devono essere installati separatamente per le rispettive conversioni.
