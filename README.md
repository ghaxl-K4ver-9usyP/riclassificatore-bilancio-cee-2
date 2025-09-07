# 📊 Riclassificatore Bilancio CEE

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io/yourusername/riclassificatore-bilancio-cee)

## 🎯 Descrizione

Applicazione web professionale per la riclassificazione automatica dei bilanci aziendali secondo lo schema CEE (Comunità Economica Europea). Il sistema analizza automaticamente i conti e li organizza secondo la struttura standard del bilancio civilistico.

## ✨ Funzionalità Principali

- 📁 **Multi-formato**: Supporta CSV, Excel (XLSX/XLS), PDF e JSON
- 🤖 **Classificazione Automatica**: Riconosce e classifica automaticamente i conti
- 📊 **Visualizzazione Interattiva**: Tabelle dinamiche e metriche in tempo reale
- 💾 **Export Professionale**: Genera report in HTML e JSON
- 🎨 **Interfaccia Moderna**: Design responsive e user-friendly
- ⚡ **Processing Real-time**: Elaborazione immediata senza attese

## 🚀 Come Utilizzare

### Online (Consigliato)
1. Visita l'app su Streamlit Cloud
2. Carica il tuo file di bilancio
3. Visualizza e scarica il report riclassificato

### Installazione Locale
```bash
# Clona il repository
git clone https://github.com/yourusername/riclassificatore-bilancio-cee.git
cd riclassificatore-bilancio-cee

# Installa dipendenze
pip install -r requirements.txt

# Avvia l'applicazione
streamlit run riclassificatore_streamlit.py
```

## 📋 Formato File Supportati

### CSV
- Separatore: punto e virgola (;)
- Colonne richieste: Codice, Descrizione, Importo/Saldo

### Excel
- Formati: .xlsx, .xls
- Supporto multi-foglio
- Riconoscimento automatico colonne

### PDF
- Estrazione automatica tabelle
- OCR per testo non strutturato

### JSON
- Struttura pre-formattata
- Import/Export configurazioni

## 🔧 Tecnologie Utilizzate

- **[Streamlit](https://streamlit.io/)** - Framework per web app
- **[Pandas](https://pandas.pydata.org/)** - Manipolazione dati
- **[PDFPlumber](https://github.com/jsvine/pdfplumber)** - Estrazione PDF
- **[OpenPyXL](https://openpyxl.readthedocs.io/)** - Gestione Excel

## 📝 Licenza

Distribuito con licenza MIT. Software libero per uso personale e commerciale.

---

⭐ Se il progetto ti è utile, considera di lasciare una stella su GitHub!