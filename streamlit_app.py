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

# --- CONFIGURAZIONE INTERMEDIARIO (GOOGLE APPS SCRIPT) ---
URL_INTERMEDIARIO_SILENZIOSO = "https://script.google.com/macros/s/AKfycbyXBLjDpJrSGHoUpuspTsNAG9f6lGhF1e8oGyJ8nkY6jZMTJo04zsT_6eLyEybGgv4/exec"

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
    except Exception:
        return None

def scarica_da_sheet(nome_scheda):
    sh = connetti_google_sheets()
    if sh is None: return pd.DataFrame()
    try:
        worksheet = sh.worksheet(nome_scheda)
        df = pd.DataFrame(worksheet.get_all_records())
        return df
    except gspread.exceptions.WorksheetNotFound:
        if "Inventario_Comodati" in nome_scheda:
            df_base = pd.DataFrame(columns=["id_bene", "tipo_bene", "descrizione", "stato"])
        elif "Registro_Comodati" in nome_scheda:
            df_base = pd.DataFrame(columns=["id_comodato", "tipo_soggetto", "nominativo", "id_bene", "data_consegna", "stato_comodato"])
        elif "Richieste_Preside" in nome_scheda:
            df_base = pd.DataFrame(columns=["id_richiesta", "data_richiesta", "richiedente", "ruolo_richiedente", "email_utente", "tipo_istanza", "categoria_bene", "oggetto", "motivazione", "stato"])
        else:
            df_base = pd.DataFrame(columns=["id", "elemento", "valore"])
        carica_su_sheet(df_base, nome_scheda)
        return df_base
    except Exception:
        return pd.DataFrame()

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
    except Exception:
        return False

def invia_notifica_nuova_richiesta(id_req, utente, ruolo, email_ut, tipo_ist, ogg, mot):
    html_ut = f"<h3>Portale Logistico Scarpa</h3><p>Gentile {utente} ({ruolo}), la tua richiesta <b>ID {id_req}</b> per '{ogg}' è stata correttamente inserita ed è in fase di valutazione dalla Dirigente.</p>"
    invia_email_sistema(email_ut, f"Richiesta ID {id_req} in lavorazione", html_ut)
    
    url_approva = f"https://magazzino-scarpa.streamlit.app/?action=approve&id={id_req}"
    url_rifiuta = f"https://magazzino-scarpa.streamlit.app/?action=reject&id={id_req}"
    html_pr = f"""
    <h2>Nuova Istanza da Autorizzare</h2>
    <p><b>Richiedente:</b> {utente} ({ruolo})<br><b>Oggetto:</b> {ogg}<br><b>Motivazione:</b> {mot}</p>
    <div style='margin-top:20px;'>
        <a href='{url_approva}' style='background:#16a34a;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;margin-right:10px;'>🟢 AUTORIZZA ADESSO</a>
        <a href='{url_rifiuta}' style='background:#dc2626;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;'>🔴 RIFIUTA</a>
    </div>
    """
    invia_email_sistema(EMAIL_PRESIDE_TEST, f"📦 NUOVA ISTANZA DA VALUTARE - ID {id_req}", html_pr)

def invia_notifica_approvata_preside(id_req, email_ut, ogg, categoria_bene):
    if categoria_bene == "PC Notebook":
        destinazione = "passata ai Tecnici Informatici per la configurazione hardware."
    else:
        destinazione = "trasmessa direttamente all'Ufficio Tecnico/Magazzino per il ritiro."
    html = f"<h3>Ottime notizie!</h3><p>La tua richiesta <b>ID {id_req}</b> per '{ogg}' è stata <b>autorizzata dalla Dirigente</b> ed è {destinazione}</p>"
    invia_email_sistema(email_ut, f"Richiesta ID {id_req} Autorizzata dalla Dirigente", html)

def invia_notifica_pronto_ritiro(id_req, email_ut, ogg):
    html = f"<h3>Pronto per il ritiro!</h3><p>Il materiale relativo alla tua richiesta <b>ID {id_req} ({ogg})</b> è pronto. Puoi recarti presso l'Ufficio Tecnico/Magazzino per il ritiro e la firma del verbale.</p>"
    invia_email_sistema(email_ut, f"Materiale pronto per il ritiro - ID {id_req}", html)

# --- CLASSE PDF MINISTERIALE ---
class PDFMinisteriale(FPDF):
    def footer(self):
        self.set_y(-20)
        self.set_draw_color(180, 180, 180)
        self.set_line_width(0.1)
        self.line(15, self.get_y(), 195, self.get_y())
        self.set_font("Arial", "", 7)
        self.cell(180, 4, 'ISISS "A. SCARPA"      Via Primo Maggio, 3 31045 Motta di Livenza (Tv)      C.F. 94071460268      Codice univoco UFOA6X', ln=True, align="C")

def pulisci_caratteri_fpdf(testo):
    mappa = {"à": "a'", "á": "a'", "è": "e'", "é": "e'", "ì": "i'", "ò": "o'", "ù": "u'"}
    for k, v in mappa.items(): testo = testo.replace(k, v)
    return testo.encode('raw_unicode_escape').decode('utf-8').encode('latin1', 'replace').decode('latin1')

def genera_pdf_comodato(id_contratto, nome, ruolo, bene, data, firma_base64=None, utente_loggato="Ufficio Tecnico"):
    if not FPDF_AVAILABLE: return b"Errore PDF"
    pdf = PDFMinisteriale()
    pdf.add_page()
    try: pdf.image(URL_LOGO, x=15, y=10, w=180); pdf.set_y(32)
    except Exception: pdf.set_font("Times", "B", 13); pdf.cell(180, 6, "ISISS ANTONIO SCARPA", ln=True, align="C")
    
    pdf.set_font("Times", "", 10)
    pdf.cell(90, 5, "Protocollo n. (vedi segnatura)", ln=False)
    pdf.cell(90, 5, f"Motta di Livenza, {data.split(' ')[0]}", ln=True, align="R")
    pdf.ln(5)
    pdf.set_font("Times", "B", 10)
    pdf.cell(95, 5, "", ln=False)
    pdf.cell(85, 5, f"Al Sig./Sigg. {nome} ({ruolo})", ln=True)
    pdf.ln(5)
    pdf.cell(22, 5, "OGGETTO: ", ln=False)
    pdf.set_font("Times", "", 10)
    pdf.multi_cell(158, 5, f"Verbale di Consegna Bene d'Istituto - ID Registro {id_contratto}")
    pdf.ln(5)
    
    corpo = f"Con la presente si attesta la consegna del bene (Identificativo: {bene}) a favore di {nome}. Il richiedente si dichiara custode responsabile dell'oggetto integro ai fini delle attivita istituzionali della scuola."
    pdf.multi_cell(180, 6, pulisci_caratteri_fpdf(corpo))
    
    pdf.set_y(-55)
    y_f = pdf.get_y()
    pdf.cell(100, 5, f"F.to l'Amministratore ({utente_loggato})")
    pdf.cell(80, 5, "Firma del Richiedente:")
    
    if firma_base64 and len(firma_base64) > 100:
        try:
            img_data = base64.b64decode(firma_base64.split(",")[1])
            img_buffer = io.BytesIO(img_data)
            pdf.image(img_buffer, x=125, y=y_f + 5, w=40)
        except Exception: pdf.cell(80, 5, "[Firma Acquisita]")
    return pdf.output()

def carica_su_drive_unico(file_bytes, nome_file, mime_type, nome_cartella_dest):
    if not GOOGLE_DRIVE_AVAILABLE: return None
    creds_info = dict(st.secrets["google_creds"]) if "google_creds" in st.secrets else dict(st.secrets["gcp_service_account"])
    try:
        creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n").strip()
        creds = service_account.Credentials.from_service_account_info(creds_info, scopes=['https://www.googleapis.com/auth/drive'])
        service = googleapiclient.discovery.build('drive', 'v3', credentials=creds)
        meta = {'name': nome_file, 'parents': [ID_CARTELLA_DRIVE_PRINCIPALE]}
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)
        service.files().create(body=meta, media_body=media, fields='id', supportsAllDrives=True).execute()
        return True
    except Exception: return None

# --- GESTORE DEL REINDIRIZZAMENTO RAPIDO (PRESIDE) ---
query_params = st.query_params
if "action" in query_params and "id" in query_params:
    azione = query_params["action"]
    id_req = query_params["id"]
    
    st.markdown("<h2 style='text-align:center;'>Elaborazione Decisione Dirigente...</h2>", unsafe_allow_html=True)
    df_f = scarica_da_sheet("Richieste_Preside")
    if not df_f.empty and "id_richiesta" in df_f.columns:
        df_f["id_richiesta"] = df_f["id_richiesta"].astype(str)
        idx_lista = df_f.index[df_f["id_richiesta"] == str(id_req)].tolist()
        if idx_lista:
            idx = idx_lista[0]
            
            if azione == "approve":
                nuovo_stato = "In lavorazione" if df_f.at[idx, "categoria_bene"] == "PC Notebook" else "Lavorata"
            else:
                nuovo_stato = "Rifiutata"
                
            df_f.at[idx, "stato"] = nuovo_stato
            carica_su_sheet(df_f, "Richieste_Preside")
            
            if azione == "approve":
                invia_notifica_approvata_preside(id_req, df_f.at[idx, "email_utente"], df_f.at[idx, "oggetto"], df_f.at[idx, "categoria_bene"])
                if df_f.at[idx, "categoria_bene"] != "PC Notebook":
                    invia_notifica_pronto_ritiro(id_req, df_f.at[idx, "email_utente"], df_f.at[idx, "oggetto"])
            st.success("✅ Decisione registrata e flussi aggiornati correttamente!")
        else: st.error("Richiesta non trovata.")
    st.stop()

# --- INIZIALIZZAZIONE SESSION STATE ---
if "ruolo_utente" not in st.session_state: st.session_state.ruolo_utente = None
if "utente_corrente" not in st.session_state: st.session_state.utente_corrente = ""
if "ruolo_specifico" not in st.session_state: st.session_state.ruolo_specifico = ""
if "magazzino_selezionato" not in st.session_state: st.session_state.magazzino_selezionato = None

# --- PORTALE DI LOGIN ---
if st.session_state.ruolo_utente is None:
    col_l, col_c, col_r = st.columns([1, 1.8, 1])
    with col_c:
        st.markdown("<h2 style='text-align: center;'>Piattaforma Logistica di Istituto</h2>", unsafe_allow_html=True)
        with st.container(border=True):
            scelta = st.radio("Seleziona profilo d'accesso:", [
                "📝 Collaboratore / Alunno / Docente (Invia Richiesta)",
                "🔑 Staff Magazzino / Amministrazione / Tecnici"
            ])
            if "Collaboratore" in scelta:
                nome = st.text_input("Nome e Cognome del Richiedente:")
                ruolo = st.selectbox("Seleziona il tuo Ruolo:", ["Alunno", "Docente", "Personale ATA", "Collaboratore Scolastico"])
                email_ut = st.text_input("Inserisci la tua Email istituzionale:")
                if st.button("Accedi al Modulo Richieste", type="primary", use_container_width=True):
                    if nome.strip() and email_ut.strip():
                        st.session_state.ruolo_utente = "collaboratore"
                        st.session_state.utente_corrente = nome.strip()
                        st.session_state.ruolo_specifico = ruolo
                        st.session_state.email_utente = email_ut.strip()
                        st.rerun()
                    else: st.error("Compila tutti i campi obbligatori.")
            else:
                pwd = st.text_input("Codice autorizzazione staff:", type="password")
                if st.button("Autentica ed Entra", type="primary", use_container_width=True):
                    if pwd in PASSWORD_MAP:
                        st.session_state.ruolo_utente = "magazziniere"
                        st.session_state.magazzino_selezionato = PASSWORD_MAP[pwd]
                        st.session_state.utente_corrente = PASSWORD_MAP[pwd]
                        st.rerun()
                    elif pwd == PASSWORD_ADMIN:
                        st.session_state.ruolo_utente = "admin"
                        st.session_state.utente_corrente = "Ufficio Tecnico (Admin)"
                        st.rerun()
                    else: st.error("Codice non valido.")
else:
    col_t, col_b_logout = st.columns([4, 1])
    with col_t: 
        inf = f"Utente: **{st.session_state.utente_corrente.upper()}**"
        if st.session_state.ruolo_specifico: inf += f" ({st.session_state.ruolo_specifico})"
        st.markdown(inf)
    with col_b_logout:
        if st.button("🚪 Esci", use_container_width=True):
            st.session_state.ruolo_utente = None; st.rerun()
    st.image(URL_LOGO, use_container_width=True)

    df_istanze = scarica_da_sheet("Richieste_Preside")

    # ==========================================
    # WORKFLOW 1: COLLABORATORE / DOCENTE / ALUNNO
    # ==========================================
    if st.session_state.ruolo_utente == "collaboratore":
        st.markdown(f"### Modulo Richieste Logistiche per: {st.session_state.ruolo_specifico}")
        if st.session_state.ruolo_specifico in ["Alunno", "Docente"]:
            categorie_disponibili = ["PC Notebook", "Chiave d'Accesso"]
            tipo_istanza_default = "Comodato d'Uso Dispositivo"
        else:
            categorie_disponibili = ["Cancelleria", "Carta e Consumabili", "Materiale d'Officina"]
            tipo_istanza_default = "Materiale Logistico / Consumo"

        with st.form("mod_rich_divise"):
            cat_b = st.selectbox("Seleziona Bene richiesto:", categorie_disponibili)
            obj_b = st.text_input("Oggetto della Richiesta:")
            mot_b = st.text_area("Motivazione dettagliata per la Direzione:")
            
            if st.form_submit_button("Invia Istanza alla Dirigente", use_container_width=True):
                if obj_b.strip() and mot_b.strip():
                    try:
                        id_r_num = pd.to_numeric(df_istanze["id_richiesta"], errors='coerce')
                        nuovo_id = int(id_r_num.max()) + 1 if not df_istanze.empty and not id_r_num.dropna().empty else 101
                    except Exception: nuovo_id = 101
                    
                    nuova_r = pd.DataFrame([{
                        "id_richiesta": nuovo_id, "data_richiesta": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "richiedente": st.session_state.utente_corrente, "ruolo_richiedente": st.session_state.ruolo_specifico,
                        "email_utente": st.session_state.email_utente, "tipo_istanza": tipo_istanza_default,
                        "categoria_bene": cat_b, "oggetto": obj_b.strip(), "motivazione": mot_b.strip(),
                        "stato": "In attesa di approvazione"
                    }])
                    carica_su_sheet(pd.concat([df_istanze, nuova_r], ignore_index=True), "Richieste_Preside")
                    invia_notifica_nuova_richiesta(nuovo_id, st.session_state.utente_corrente, st.session_state.ruolo_specifico, st.session_state.email_utente, tipo_istanza_default, obj_b.strip(), mot_b.strip())
                    st.success(f"Richiesta ID {nuovo_id} inoltrata!")

    # ==========================================
    # WORKFLOW 2: TECNICI INFORMATICI
    # ==========================================
    elif st.session_state.ruolo_utente == "magazziniere" and st.session_state.magazzino_selezionato == "Tecnici Informatici":
        st.markdown("<h2>💻 Dashboard Preparazione Tecnici Informatici</h2>", unsafe_allow_html=True)
        da_lavorare = df_istanze[(df_istanze["stato"] == "In lavorazione") & (df_istanze["categoria_bene"] == "PC Notebook")] if not df_istanze.empty else pd.DataFrame()
        
        if da_lavorare.empty: st.info("Nessun PC da configurare o preparare al momento.")
        else:
            for _, riga in da_lavorare.iterrows():
                with st.container(border=True):
                    st.markdown(f"🛠️ **Richiesta ID {riga['id_richiesta']}** | Destinatario: **{riga['richiedente']}** ({riga['ruolo_richiedente']})")
                    st.markdown(f"**Oggetto:** {riga['oggetto']} — **Motivazione:** {riga['motivazione']}")
                    if st.button(f"Marca come LAVORATA (PC Pronto al ritiro) ## ID {riga['id_richiesta']}", use_container_width=True):
                        idx = df_istanze.index[df_istanze["id_richiesta"].astype(str) == str(riga['id_richiesta'])].tolist()[0]
                        df_istanze.at[idx, "stato"] = "Lavorata"
                        carica_su_sheet(df_istanze, "Richieste_Preside")
                        invia_notifica_pronto_ritiro(riga['id_richiesta'], riga['email_utente'], riga['oggetto'])
                        st.success("Stato aggiornato!")
                        st.rerun()

    # ==========================================
    # WORKFLOW 3: ADMIN (CONSEGNA & PAD ORIGINALE HTML5)
    # ==========================================
    elif st.session_state.ruolo_utente == "admin":
        st.markdown("## 👑 Ufficio Amministrazione e Consegne Fisiche")
        tab_pronte, tab_tutti_comodati, tab_registro_completo = st.tabs(["📦 PRATICHE PRONTE PER CONSEGNA", "📋 INVENTARIO COMODATI", "📜 REGISTRO STORICO"])
        
        with tab_pronte:
            pronte = df_istanze[df_istanze["stato"] == "Lavorata"] if not df_istanze.empty else pd.DataFrame()
            if pronte.empty: st.info("Nessun materiale o dispositivo in attesa di consegna fisica.")
            else:
                for _, riga in pronte.iterrows():
                    with st.expander(f"📦 ID {riga['id_richiesta']} - Consegna a {riga['richiedente']} [{riga['categoria_bene']}]"):
                        st.markdown(f"**Dettagli istanza:** {riga['oggetto']} — *Nota:* {riga['motivazione']}")
                        
                        df_inv_c = scarica_da_sheet("Inventario_Comodati")
                        disp = df_inv_c[df_inv_c["stato"] == "Disponibile"]["id_bene"].tolist() if not df_inv_c.empty else []
                        
                        col1, col2 = st.columns([1, 1.2])
                        with col1:
                            if riga['categoria_bene'] in ["PC Notebook", "Chiave d'Accesso"]:
                                bene_assegnato = st.selectbox("Seleziona seriale fisico da assegnare:", disp, key=f"b_{riga['id_richiesta']}")
                            else:
                                bene_assegnato = st.text_input("Lotto / Quantità materiale consegnato:", value="1 Conf.", key=f"b_{riga['id_richiesta']}")
                            
                            # Questo campo di testo nascosto riceve la firma base64 dall'HTML5 Canvas sottostante
                            firma_b64 = st.text_input("Codice Firma Acquisito:", key=f"f_{riga['id_richiesta']}", label_visibility="collapsed")
                            
                            if st.button(f"Completa Consegna e Genera Verbale ## {riga['id_richiesta']}", type="primary"):
                                if firma_b64.startswith("data:image/png;base64,"):
                                    df_reg_c = scarica_da_sheet("Registro_Comodati")
                                    id_comodato_numerico = pd.to_numeric(df_reg_c["id_comodato"], errors='coerce')
                                    id_com = int(id_comodato_numerico.max()) + 1 if not df_reg_c.empty and not id_comodato_numerico.dropna().empty else 1001
                                    
                                    data_ora = datetime.now().strftime("%d/%m/%Y %H:%M")
                                    pdf_bytes = genera_pdf_comodato(id_com, riga['richiedente'], riga['ruolo_richiedente'], bene_assegnato, data_ora, firma_b64, st.session_state.utente_corrente)
                                    
                                    if carica_su_drive_unico(pdf_bytes, f"Verbale_{id_com}_{riga['richiedente']}.pdf", "application/pdf", "Verbali_Logistica"):
                                        idx = df_istanze.index[df_istanze["id_richiesta"].astype(str) == str(riga['id_richiesta'])].tolist()[0]
                                        df_istanze.at[idx, "stato"] = "Assegnata"
                                        carica_su_sheet(df_istanze, "Richieste_Preside")
                                        
                                        nuovo_c = pd.DataFrame([{"id_comodato": id_com, "tipo_soggetto": riga['ruolo_richiedente'], "nominativo": riga['richiedente'], "id_bene": bene_assegnato, "data_consegna": data_ora, "stato_comodato": "Chiuso/Consegnato"}])
                                        carica_su_sheet(pd.concat([df_reg_c, nuovo_c], ignore_index=True), "Registro_Comodati")
                                        
                                        if riga['categoria_bene'] in ["PC Notebook", "Chiave d'Accesso"]:
                                            df_inv_c.loc[df_inv_c["id_bene"] == bene_assegnato, "stato"] = "Assegnato"
                                            carica_su_sheet(df_inv_c, "Inventario_Comodati")
                                            
                                        st.success("Pratica Evasa! Verbale ufficiale registrato e caricato.")
                                        st.rerun()
                                else:
                                    st.error("⚠️ Nessuna firma rilevata. Usa il riquadro a destra per firmare prima di inviare.")
                        
                        with col2:
                            st.markdown("**✍️ Firma del Richiedente (Touch/Mouse):**")
                            # IL NOSTRO COMPONENTE ORIGINALE HTML5 INIETTATO SENZA LIBRERIE
                            html_firma_componente = f"""
                            <div style="border:2px dashed #cbd5e1; border-radius:8px; background:#ffffff; padding:5px; width:360px;">
                                <canvas id="canvas_firma" width="350" height="150" style="cursor:crosshair; background:#ffffff;"></canvas>
                                <div style="margin-top:5px; text-align:right;">
                                    <button onclick="pulisciCanvas()" style="background:#f1f5f9; border:1px solid #cbd5e1; border-radius:4px; padding:3px 8px; font-size:12px; cursor:pointer;">Cancella</button>
                                </div>
                            </div>
                            <script>
                                var canvas = document.getElementById('canvas_firma');
                                var ctx = canvas.getContext('2d');
                                var inDisegno = false;

                                function prendiCoordinate(e) {{
                                    var rect = canvas.getBoundingClientRect();
                                    if(e.touches && e.touches.length > 0) {{
                                        return {{ x: e.touches[0].clientX - rect.left, y: e.touches[0].clientY - rect.top }};
                                    }}
                                    return {{ x: e.clientX - rect.left, y: e.clientY - rect.top }};
                                }}

                                function inizia(e) {{ inDisegno = true; ctx.beginPath(); var p = prendiCoordinate(e); ctx.moveTo(p.x, p.y); }}
                                function muovi(e) {{
                                    if(!inDisegno) return;
                                    e.preventDefault();
                                    var p = prendiCoordinate(e);
                                    ctx.lineTo(p.x, p.y);
                                    ctx.lineWidth = 2;
                                    ctx.strokeStyle = '#000000';
                                    ctx.stroke();
                                    aggiornaStreamlit();
                                }}
                                function ferma() {{ inDisegno = false; }}
                                function pulisciCanvas() {{ ctx.clearRect(0, 0, canvas.width, canvas.height); window.parent.postMessage({{type: 'streamlit:setComponentValue', value: ''}}, '*'); }}
                                
                                function aggiornaStreamlit() {{
                                    var dataURL = canvas.toDataURL('image/png');
                                    // Invia la stringa base64 direttamente al widget padre di Streamlit
                                    window.parent.postMessage({{type: 'streamlit:setComponentValue', value: dataURL}}, '*');
                                }}

                                canvas.addEventListener('mousedown', inizia);
                                canvas.addEventListener('mousemove', muovi);
                                window.addEventListener('mouseup', ferma);
                                canvas.addEventListener('touchstart', inizia);
                                canvas.addEventListener('touchmove', muovi);
                                window.addEventListener('touchend', ferma);
                            </script>
                            """
                            # Visualizzazione del pad interattivo nativo
                            st.components.v1.html(html_firma_componente, height=200)

        with tab_tutti_comodati:
            st.dataframe(scarica_da_sheet("Inventario_Comodati"), use_container_width=True, hide_index=True)
        with tab_registro_completo:
            st.dataframe(df_istanze, use_container_width=True, hide_index=True)

    # ==========================================
    # WORKFLOW 4: ALTRI MAGAZZINI
    # ==========================================
    elif st.session_state.ruolo_utente == "magazziniere":
        st.markdown(f"## 📦 Magazzino Standard: {st.session_state.magazzino_selezionato}")
        st.dataframe(scarica_da_sheet(MAPPA_SCHEDE[st.session_state.magazzino_selezionato]["inventario"]), use_container_width=True, hide_index=True)
