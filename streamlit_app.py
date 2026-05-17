import streamlit as st
import pandas as pd
from datetime import datetime
import io
import base64
from PIL import Image
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- IMPORTAZIONE SICURA E INGEGNERIZZATA DEL NUOVO MODULO ---
try:
    from gestione_preventivi import mostra_interfaccia_preventivi
    MODULO_PREVENTIVI_DISPONIBILE = True
except Exception:
    MODULO_PREVENTIVI_DISPONIBILE = False

# --- CONFIGURAZIONE INTERMEDIARIO (GOOGLE APPS SCRIPT) ---
URL_INTERMEDIARIO_SILENZIOSO = "https://script.google.com/macros/s/AKfycbyXBLjDpJrSGHoUpuspTsNAG9f6lGhF1e8oGyJ8nkY6jZMTJo04zsT_6eLyEybGgv4/exec"

# --- CONFIGURAZIONE DRIVE COMODATI (CONSEGNA / RICONSEGNA) ---
ID_CARTELLA_CONSEGNE = "1pJpYtIfcMEKFh62rSOGTXWYG8CgvzN4m"
ID_CARTELLA_RICONSEGNE = "1S6IcauDOc-8sFiCdGv67CHKf_H9u7BVW"

# --- CONTROLLO LIBRERIE ESTERNE ---
try:
    import gspread
    from google.oauth2 import service_account
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

try:
    import googleapiclient.discovery
    from googleapiclient.http import MediaIoBaseUpload
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False

try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False

# --- CONFIGURAZIONE INIZIALE DI PAGINA ---
st.set_page_config(page_title="Gestione Magazzini Scarpa", page_icon="🏢", layout="wide")

# --- COSTANTI E CONFIGURAZIONI TIPO ---
PASSWORD_MAP = {
    "ata2026": "Personale ATA",
    "officina2026": "Officina",
    "tecnici2026": "Tecnici Informatici"
}
PASSWORD_ADMIN = "admin99"

MAPPA_SCHEDE = {
    "Personale ATA": {"inventario": "Inventario ata", "richieste": "Richieste ata"},
    "Officina": {"inventario": "Inventario officina", "richieste": "Richieste officina"},
    "Tecnici Informatici": {"inventario": "Inventario informatica", "richieste": "Richieste informatica"}
}

URL_LOGO = "https://cspace.spaggiari.eu//pub/TVII0004/TVII0004-intestazione-nuova-senzaloghi.png?_t=1712923868"
ID_CARTELLA_DRIVE_PRINCIPALE = "1bVTs2smvVJONs2oIAFZdDvX9pYDK9MZT"
SPREADSHEET_ID = "1Q91H_TULvpsnPcyOwQ1lxmjOf809xp4cUz9p1EdMc-4"
LISTA_MAGAZZINI = ["Personale ATA", "Officina", "Tecnici Informatici"]

EMAIL_PRESIDE_TEST = "marcobrunetti14@gmail.com" 

# --- STILE PREMIUM ISTITUZIONALE ---
st.markdown("""
    <style>
        .stApp { background-color: #f8fafc; }
        [data-testid="stVerticalBlockBorderWrapper"] {
            background: white !important;
            padding: 30px !important;
            border-radius: 16px !important;
            border: 1px solid #e2e8f0 !important;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05) !important;
        }
        div.stButton > button:first-child {
            background-color: #8b1e1e !important;
            color: white !important;
            border-radius: 10px !important;
            border: none !important;
            font-weight: 600 !important;
            padding: 12px 24px !important;
        }
        div.stButton > button:first-child:hover { background-color: #a72828 !important; }
        .stTextInput input, .stSelectbox div[data-baseweb="select"] { border-radius: 10px !important; }
        h2, h3 { color: #0f172a !important; font-weight: 700; }
    </style>
""", unsafe_allow_html=True)

# --- CONNESSIONE GOOGLE SHEETS ---
@st.cache_resource(ttl=2)
def connetti_google_sheets():
    if not GSPREAD_AVAILABLE: return None
    creds_info = None
    if "google_creds" in st.secrets: creds_info = dict(st.secrets["google_creds"])
    elif "gcp_service_account" in st.secrets: creds_info = dict(st.secrets["gcp_service_account"])
    if not creds_info: return None
    try:
        if "private_key" in creds_info: creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n").strip()
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = service_account.Credentials.from_service_account_info(creds_info, scopes=scopes)
        return gspread.authorize(creds).open_by_key(SPREADSHEET_ID)
    except Exception: return None

def scarica_da_sheet(nome_scheda):
    sh = connetti_google_sheets()
    if sh is None: return pd.DataFrame()
    try:
        worksheet = sh.worksheet(nome_scheda)
        return pd.DataFrame(worksheet.get_all_records())
    except gspread.exceptions.WorksheetNotFound:
        if "Inventario_Comodati" in nome_scheda:
            df_base = pd.DataFrame(columns=["id_bene", "tipo_bene", "descrizione", "stato"])
        elif "Registro_Comodati" in nome_scheda:
            df_base = pd.DataFrame(columns=["id_comodato", "tipo_soggetto", "nominativo", "id_bene", "data_consegna", "stato_comodato"])
        elif "Richieste_Preside" in nome_scheda:
            df_base = pd.DataFrame(columns=["id_richiesta", "data_richiesta", "richiedente", "ruolo_richiedente", "email_utente", "tipo_istanza", "categoria_bene", "oggetto", "motivazione", "stato"])
        elif "Richieste_Preventivo_Magazzino" in nome_scheda:
            df_base = pd.DataFrame(columns=["id_richiesta_mag", "data_creazione", "magazzino_origine", "materiale_richiesto", "quantita_esimata", "stato_iter", "note"])
        elif "Registro_Preventivi" in nome_scheda:
            df_base = pd.DataFrame(columns=["id_preventivo", "id_richiesta_mag", "fornitore", "importo_ivato", "data_inserimento", "stato_approvazione", "note"])
        elif "Anagrafica_Fornitori" in nome_scheda:
            df_base = pd.DataFrame(columns=["id_fornitore", "ragione_sociale", "partita_iva", "email_contatto"])
        else:
            df_base = pd.DataFrame(columns=["id", "elemento", "valore"])
        carica_su_sheet(df_base, nome_scheda)
        return df_base
    except Exception: return pd.DataFrame()

def carica_su_sheet(df, nome_scheda):
    sh = connetti_google_sheets()
    if sh is None: return
    try:
        try: worksheet = sh.worksheet(nome_scheda)
        except gspread.exceptions.WorksheetNotFound: worksheet = sh.add_worksheet(title=nome_scheda, rows="1000", cols="20")
        worksheet.clear()
        df_pulito = df.fillna("")
        for col in df_pulito.columns: df_pulito[col] = df_pulito[col].astype(str)
        valori = [df_pulito.columns.values.tolist()] + df_pulito.values.tolist()
        worksheet.update(valori)
    except Exception: pass

# --- MOTORE NOTIFICHE EMAIL ---
def invia_email_sistema(destinatario, oggetto_mail, html_corpo):
    if "email_config" not in st.secrets: return False
    try:
        cfg = st.secrets["email_config"]
        msg = MIMEMultipart('alternative')
        msg['From'] = cfg.get("smtp_user")
        msg['To'] = destinatario
        msg['Subject'] = oggetto_mail
        msg.attach(MIMEText(html_corpo, 'html', 'utf-8'))
        server = smtplib.SMTP(cfg.get("smtp_server", "smtp.gmail.com"), int(cfg.get("smtp_port", 587)))
        server.starttls()
        server.login(cfg.get("smtp_user"), cfg.get("smtp_password"))
        server.sendmail(cfg.get("smtp_user"), destinatario, msg.as_string())
        server.quit()
        return True
    except Exception: return False

def invia_notifica_nuova_richiesta(id_req, utente, ruolo, email_ut, tipo_ist, ogg, mot):
    html_ut = f"<h3>Portale Logistico Scarpa</h3><p>Gentile {utente} ({ruolo}), la tua richiesta <b>ID {id_req}</b> per '{ogg}' è stata correttamente inserita ed è in fase di valutazione dalla Dirigente.</p>"
    invia_email_sistema(email_ut, f"Richiesta ID {id_req} in lavorazione", html_ut)
    url_approva = f"https://magazzino-scarpa.streamlit.app/?action=approve&id={id_req}"
    url_rifiuta = f"https://magazzino-scarpa.streamlit.app/?action=reject&id={id_req}"
    html_pr = f"""<h3>Nuova Istanza da Autorizzare</h3><p><b>Richiedente:</b> {utente}<br><b>Oggetto:</b> {ogg}<br><b>Motivazione:</b> {mot}</p>
    <div style='margin-top:20px;'><a href='{url_approva}' style='background:#16a34a;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;'>🟢 AUTORIZZA</a></div>"""
    invia_email_sistema(EMAIL_PRESIDE_TEST, f"📦 NUOVA ISTANZA - ID {id_req}", html_pr)

# --- CLASSE PDF MINISTERIALE ---
class PDFMinisteriale(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "", 7)
        footer_text = 'ISISS "A. SCARPA"  Via Primo Maggio, 3 Motta di Livenza  C.F. 94071460268'
        self.cell(180, 4, pulisci_caratteri_fpdf(footer_text), ln=True, align="C")

def pulisci_caratteri_fpdf(testo):
    return testo.encode('raw_unicode_escape').decode('utf-8').encode('latin1', 'replace').decode('latin1')

def genera_pdf_comodato(id_contratto, nome, ruolo, bene, data, tipo_operazione="Consegna", firma_base64=None, utente_loggato="Ufficio Tecnico"):
    if not FPDF_AVAILABLE: return b"Errore"
    pdf = PDFMinisteriale()
    pdf.add_page()
    pdf.set_font("Times", "B", 12)
    pdf.cell(180, 6, pulisci_caratteri_fpdf(f"Verbale di {tipo_operazione} - ID {id_contratto}"), ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("Times", "", 11)
    pdf.multi_cell(180, 6, pulisci_caratteri_fpdf(f"Assegnato a {nome} ({ruolo}) il bene identificato come: {bene} in data {data}."))
    
    if firma_base64 and len(firma_base64) > 100:
        try:
            dati_f = firma_base64.split(",")[1] if "," in firma_base64 else firma_base64
            img_data = base64.b64decode(dati_f)
            pdf.image(io.BytesIO(img_data), x=120, y=100, w=40)
        except Exception: pdf.text(120, 100, "[Firma Digitale]")
    return pdf.output()

def carica_su_drive_unico(file_bytes, nome_file, mime_type, id_cartella_destinazione):
    if not GOOGLE_DRIVE_AVAILABLE: return None
    try:
        creds_info = dict(st.secrets["google_creds"])
        creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n").strip()
        creds = service_account.Credentials.from_service_account_info(creds_info, scopes=['https://www.googleapis.com/auth/drive'])
        service = googleapiclient.discovery.build('drive', 'v3', credentials=creds)
        meta = {'name': nome_file, 'parents': [id_cartella_destinazione]}
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)
        service.files().create(body=meta, media_body=media, fields='id', supportsAllDrives=True).execute()
        return True
    except Exception: return False

def mostra_pad_firma(chiave_id):
    html_pad = f"""<canvas id="canvas_{chiave_id}" width="400" height="120" style="border:1px solid #000; background:#fff;"></canvas>
    <br><button onclick="window.parent.postMessage(document.getElementById('canvas_{chiave_id}').toDataURL(), '*')">Conferma Firma</button>"""
    st.components.v1.html(html_pad, height=160)

# --- INIZIALIZZAZIONE SESSION STATE ---
if "ruolo_utente" not in st.session_state: st.session_state.ruolo_utente = None
if "utente_corrente" not in st.session_state: st.session_state.utente_corrente = ""
if "ruolo_specifico" not in st.session_state: st.session_state.ruolo_specifico = ""
if "magazzino_selezionato" not in st.session_state: st.session_state.magazzino_selezionato = None

# --- PORTALE DI LOGIN ---
if st.session_state.ruolo_utente is None:
    st.markdown("<h2 style='text-align: center;'>Piattaforma Logistica di Istituto</h2>", unsafe_allow_html=True)
    scelta = st.radio("Profilo:", ["📝 Utente Interno (Docente/ATA)", "🔑 Staff Logistico / Admin"])
    if "Utente" in scelta:
        nome = st.text_input("Nome e Cognome:")
        ruolo = st.selectbox("Ruolo:", ["Docente", "Personale ATA", "Alunno"])
        em = st.text_input("Email:")
        if st.button("Accedi"):
            st.session_state.ruolo_utente = "collaboratore"
            st.session_state.utente_corrente = nome
            st.session_state.ruolo_specifico = ruolo
            st.session_state.email_utente = em
            st.rerun()
    else:
        pwd = st.text_input("Password:", type="password")
        if st.button("Entra"):
            if pwd in PASSWORD_MAP:
                st.session_state.ruolo_utente = "magazziniere"
                st.session_state.magazzino_selezionato = PASSWORD_MAP[pwd]
                st.session_state.utente_corrente = PASSWORD_MAP[pwd]
                st.rerun()
            elif pwd == PASSWORD_ADMIN:
                st.session_state.ruolo_utente = "admin"
                st.session_state.utente_corrente = "Ufficio Tecnico (Admin)"
                st.rerun()
else:
    if st.button("🚪 Esci"):
        st.session_state.ruolo_utente = None
        st.rerun()

    df_istanze = scarica_da_sheet("Richieste_Preside")

    # ==========================================
    # INTERFACCIA COLLABORATORE / UTENTE INTERNO
    # ==========================================
    if st.session_state.ruolo_utente == "collaboratore":
        with st.form("richiesta_ut"):
            cat = st.selectbox("Categoria:", ["PC Notebook", "Cancelleria", "Materiale Logistico"])
            obj = st.text_input("Oggetto:")
            mot = st.text_area("Motivazione:")
            if st.form_submit_button("Invia Richiesta"):
                id_r = 101 if df_istanze.empty else int(pd.to_numeric(df_istanze["id_richiesta"], errors='coerce').max()) + 1
                nuova = pd.DataFrame([{"id_richiesta": id_r, "data_richiesta": datetime.now().strftime("%d/%m/%Y %H:%M"), "richiedente": st.session_state.utente_corrente, "ruolo_richiedente": st.session_state.ruolo_specifico, "email_utente": st.session_state.email_utente, "tipo_istanza": "Standard", "categoria_bene": cat, "oggetto": obj, "motivazione": mot, "stato": "In attesa di approvazione"}])
                carica_su_sheet(pd.concat([df_istanze, nuova], ignore_index=True), "Richieste_Preside")
                st.success("Richiesta registrata!")

    # ==========================================
    # INTERFACCIA ADMIN (UFFICIO TECNICO)
    # ==========================================
    elif st.session_state.ruolo_utente == "admin":
        with st.sidebar:
            sezione_selezionata = st.radio("Menu Admin:", ["📦 Giacenza dei Magazzini", "📋 Richieste Personale ATA", "🔄 Gestione Comodati d'Uso", "📊 Gestione Preventivi e Fornitori"])
        
        if sezione_selezionata == "📦 Giacenza dei Magazzini":
            st.dataframe(df_istanze, use_container_width=True, hide_index=True)
        elif sezione_selezionata == "🔄 Gestione Comodati d'Uso":
            st.write("Area Comodati e stampe Verbali PDF attiva.")
        elif sezione_selezionata == "📊 Gestione Preventivi e Fornitori":
            if MODULO_PREVENTIVI_DISPONIBILE:
                mostra_interfaccia_preventivi(scarica_da_sheet, carica_su_sheet, invia_email_sistema, URL_INTERMEDIARIO_SILENZIOSO, df_istanze)
            else:
                st.info("Modulo preventivi non pronto.")

    # ==========================================
    # INTERFACCIA MAGAZZINIERE (CON INSERIMENTO RICHIESTE FABBISOGNO)
    # ==========================================
    elif st.session_state.ruolo_utente == "magazziniere":
        st.markdown(f"## 📦 Magazzino: {st.session_state.magazzino_selezionato}")
        tab1, tab2 = st.tabs(["📋 Inventario attuale", "➕ Segnala Fabbisogno a Ufficio Tecnico"])
        
        with tab1:
            st.dataframe(scarica_da_sheet(MAPPA_SCHEDE[st.session_state.magazzino_selezionato]["inventario"]), use_container_width=True, hide_index=True)
            
        with tab2:
            st.markdown("### Inserisci materiale mancante da sottoporre a preventivo")
            with st.form("form_fabbisogno_mag"):
                mat = st.text_input("Materiale Richiesto:")
                qta = st.text_input("Quantità Stimata:")
                note = st.text_area("Note aggiuntive:")
                if st.form_submit_button("Invia Fabbisogno"):
                    df_richieste_mag = scarica_da_sheet("Richieste_Preventivo_Magazzino")
                    id_rm = 2001 if df_richieste_mag.empty else int(pd.to_numeric(df_richieste_mag["id_richiesta_mag"], errors='coerce').max()) + 1
                    nuovo_fabb = pd.DataFrame([{"id_richiesta_mag": id_rm, "data_creazione": datetime.now().strftime("%d/%m/%Y %H:%M"), "magazzino_origine": st.session_state.magazzino_selezionato, "materiale_richiesto": mat, "quantita_esimata": qta, "stato_iter": "In attesa di preventivi", "note": note}])
                    carica_su_sheet(pd.concat([df_richieste_mag, nuovo_fabb], ignore_index=True), "Richieste_Preventivo_Magazzino")
                    st.success(f"Richiesta REQ {id_rm} registrata! L'Ufficio Tecnico provvederà a richiedere i preventivi.")
