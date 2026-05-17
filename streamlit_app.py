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
        self.set_y(-15)
        self.set_font("Arial", "", 7)
        self.set_text_color(100, 100, 100)
        footer_text = 'ISISS "A. SCARPA"     Via Primo Maggio, 3 31045 Motta di Livenza (Tv)      C.F. 94071460268      Codice univoco UFOA6X'
        self.cell(180, 4, pulisci_caratteri_fpdf(footer_text), ln=True, align="C")
        footer_links = 'tvis01100a@istruzione.it     tvis01100a@pec.istruzione.it'
        self.cell(180, 4, pulisci_caratteri_fpdf(footer_links), ln=True, align="C")

def pulisci_caratteri_fpdf(testo):
    mappa = { "à": "a'", "á": "a'", "è": "e'", "é": "e'", "ì": "i'", "ò": "o'", "ù": "u'" }
    for k, v in mappa.items(): testo = testo.replace(k, v)
    return testo.encode('raw_unicode_escape').decode('utf-8').encode('latin1', 'replace').decode('latin1')

# --- GENERAZIONE PDF ---
def genera_pdf_comodato(id_contratto, nome, ruolo, bene, data, tipo_operazione="Consegna", firma_base64=None, utente_loggato="Ufficio Tecnico"):
    if not FPDF_AVAILABLE: return b"Errore PDF"
    pdf = PDFMinisteriale()
    pdf.add_page()
    
    try: 
        pdf.image(URL_LOGO, x=15, y=10, w=180)
        pdf.set_y(35)
    except Exception: 
        pdf.set_font("Times", "B", 13)
        pdf.cell(180, 6, "ISISS ANTONIO SCARPA", ln=True, align="C")
        pdf.set_y(35)
    
    pdf.set_font("Times", "I", 10)
    pdf.cell(90, 5, pulisci_caratteri_fpdf("Protocollo n. (vedi segnatura)"), ln=False)
    pdf.cell(90, 5, pulisci_caratteri_fpdf("Motta di Livenza, (vedi segnatura)"), ln=True, align="R")
    pdf.ln(8)
    
    pdf.set_font("Times", "B", 11)
    pdf.cell(110, 5, "", ln=False)
    pdf.cell(70, 5, pulisci_caratteri_fpdf(f"Alla componente Docente / al Personale:"), ln=True, align="L")
    pdf.set_font("Times", "", 11)
    pdf.cell(110, 5, "", ln=False)
    pdf.cell(70, 5, pulisci_caratteri_fpdf(f"{nome} ({ruolo})"), ln=True, align="L")
    pdf.ln(10)
    
    pdf.set_font("Times", "B", 11)
    pdf.cell(24, 5, "OGGETTO: ", ln=False)
    testo_oggetto = f"Verbale di {tipo_operazione} Bene d'Istituto in Comodato d'Uso - ID {id_contratto}"
    pdf.multi_cell(156, 5, pulisci_caratteri_fpdf(testo_oggetto))
    pdf.ln(12)
    
    pdf.set_font("Times", "", 11)
    if tipo_operazione.lower() == "consegna":
        corpo = (f"Con la presente si attesta la formale consegna in comodato d'uso del bene "
                 f"d'Istituto (Identificativo Bene: {bene}) a favore di {nome}. Chi riceve il bene "
                 f"costituisce parte custode e responsabile dell'oggetto integro, impegnandosi a conservarlo "
                 f"con la massima cura e la dovuta diligenza professionale, nonché ad utilizzarlo esclusivamente per le "
                 f"finalita' e le attivita' istituzionali della scuola.")
    else:
        corpo = (f"Con la presente si attesta la formale riconsegna e il conseguente rientro al magazzino del bene "
                 f"d'Istituto (Identificativo Bene: {bene}) precedentemente concesso in comodato d'uso "
                 f"a {nome}. L'Amministrazione prende in carico il dispositivo verificandone lo stato "
                 f"di restituzione ai fini del ripristino dell'inventario.")
                 
    pdf.multi_cell(180, 6, pulisci_caratteri_fpdf(corpo))
    pdf.ln(20)
    
    pdf.set_font("Times", "", 12)
    pdf.cell(180, 5, pulisci_caratteri_fpdf("La Dirigente Scolastica"), ln=True, align="C")
    pdf.set_font("Times", "B", 12)
    pdf.cell(180, 5, pulisci_caratteri_fpdf("Maria Cristina Taddeo"), ln=True, align="C")
    pdf.set_font("Times", "", 5.5)
    nota_cad = "Documento informatico firmato digitalmente ai sensi del D.Lgs 82/2005 CAD art.45, ss.mm.ii e norme collegate."
    pdf.cell(180, 4, pulisci_caratteri_fpdf(nota_cad), ln=True, align="C")
    
    pdf.set_y(-55)
    y_f = pdf.get_y()
    pdf.set_font("Times", "", 10)
    pdf.cell(100, 5, pulisci_caratteri_fpdf(f"F.to la parte Amministratrice ({utente_loggato})"))
    pdf.cell(80, 5, pulisci_caratteri_fpdf(f"Firma della persona richiedente ({tipo_operazione}):"))
    
    if firma_base64 and len(firma_base64) > 100:
        try:
            dati_f = firma_base64.split(",")[1] if "," in firma_base64 else firma_base64
            img_data = base64.b64decode(dati_f)
            img_originale = Image.open(io.BytesIO(img_data))
            
            sfondo_bianco = Image.new("RGBA", img_originale.size, "WHITE")
            sfondo_bianco.paste(img_originale, (0, 0), img_originale)
            
            img_buffer = io.BytesIO()
            sfondo_bianco.convert("RGB").save(img_buffer, format="JPEG", quality=95)
            img_buffer.seek(0)
            
            pdf.image(img_buffer, x=115, y=y_f + 6, w=50, h=0)
        except Exception: 
            pdf.text(115, y_f + 10, "[Firma Elettronica Acquisita]")
    else:
        pdf.text(115, y_f + 10, "____________________________")
        
    return pdf.output()

def carica_su_drive_unico(file_bytes, nome_file, mime_type, id_cartella_destinazione):
    if not GOOGLE_DRIVE_AVAILABLE: return None
    creds_info = dict(st.secrets["google_creds"]) if "google_creds" in st.secrets else dict(st.secrets["gcp_service_account"])
    try:
        creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n").strip()
        creds = service_account.Credentials.from_service_account_info(creds_info, scopes=['https://www.googleapis.com/auth/drive'])
        service = googleapiclient.discovery.build('drive', 'v3', credentials=creds)
        
        meta = {'name': nome_file, 'parents': [id_cartella_destinazione]}
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)
        service.files().create(body=meta, media_body=media, fields='id', supportsAllDrives=True).execute()
        return True
    except Exception: return None

def mostra_pad_firma(chiave_id):
    html_pad = f"""
    <div style="background: #f8fafc; border: 2px dashed #cbd5e1; padding: 15px; border-radius: 12px; font-family: sans-serif;">
        <canvas id="canvas_firma_{chiave_id}" width="440" height="130" style="border:2px solid #64748b; background:#ffffff; cursor:crosshair; touch-action: none; border-radius:8px;"></canvas>
        <div style="margin-top:10px; display:flex; gap:10px;">
            <button type="button" onclick="pulisciCanvas_{chiave_id}()" style="padding:6px 12px; background:#ef4444; color:white; border:none; border-radius:6px; cursor:pointer; font-weight:bold; font-size:12px;">Cancella</button>
            <button type="button" onclick="generaCodiceFirma_{chiave_id}()" style="padding:6px 12px; background:#22c55e; color:white; border:none; border-radius:6px; cursor:pointer; font-weight:bold; font-size:12px;">Genera Codice Firma</button>
        </div>
        <textarea id="output_b64_{chiave_id}" style="width:100%; height:45px; margin-top:10px; font-size:9px; color:#334155; border:1px solid #cbd5e1; border-radius:4px; display:none;" readonly></textarea>
        <p id="msg_copia_{chiave_id}" style="font-size:11px; color:#b91c1c; font-weight:bold; margin-top:5px; display:none;">Firma Codificata! Fai triplo click nella casella sopra, copia tutto il testo (Ctrl+C) e incollalo nel campo Streamlit sotto.</p>
    </div>
    <script>
        var canvas = document.getElementById('canvas_firma_{chiave_id}');
        var ctx = canvas.getContext('2d');
        ctx.strokeStyle = '#000000'; ctx.lineWidth = 3; ctx.lineCap = 'round';
        var isDrawing = false;
        function getCoordinate(e) {{
            var rect = canvas.getBoundingClientRect();
            if(e.touches && e.touches.length > 0) return {{ x: e.touches[0].clientX - rect.left, y: e.touches[0].clientY - rect.top }};
            return {{ x: e.clientX - rect.left, y: e.clientY - rect.top }};
        }}
        canvas.addEventListener('mousedown', function(e) {{ isDrawing = true; var p = getCoordinate(e); ctx.beginPath(); ctx.moveTo(p.x, p.y); }});
        canvas.addEventListener('mousemove', function(e) {{ if(!isDrawing) return; var p = getCoordinate(e); ctx.lineTo(p.x, p.y); ctx.stroke(); }});
        canvas.addEventListener('mouseup', function() {{ isDrawing = false; }});
        canvas.addEventListener('touchstart', function(e) {{ isDrawing = true; var p = getCoordinate(e); ctx.beginPath(); ctx.moveTo(p.x, p.y); e.preventDefault(); }}, {{passive: false}});
        canvas.addEventListener('touchmove', function(e) {{ if(!isDrawing) return; var p = getCoordinate(e); ctx.lineTo(p.x, p.y); ctx.stroke(); e.preventDefault(); }}, {{passive: false}});
        canvas.addEventListener('touchend', function() {{ isDrawing = false; }});
        function pulisciCanvas_{chiave_id}() {{ ctx.clearRect(0, 0, canvas.width, canvas.height); document.getElementById('output_b64_{chiave_id}').style.display = 'none'; document.getElementById('msg_copia_{chiave_id}').style.display = 'none'; }}
        function generaCodiceFirma_{chiave_id}() {{ var dataUrl = canvas.toDataURL('image/png'); var txt = document.getElementById('output_b64_{chiave_id}'); txt.value = dataUrl; txt.style.display = 'block'; document.getElementById('msg_copia_{chiave_id}').style.display = 'block'; txt.select(); }}
    </script>
    """
    st.components.v1.html(html_pad, height=230)

# --- REINDIRIZZAMENTO RAPIDO DECISIONI ---
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
            st.session_state.ruolo_utente = None
            st.rerun()
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
                    st.success(f"Richiesta ID {nuovo_id} inoltrata! La mail automatica è stata inviata al tuo indirizzo.")

    # ==========================================
    # WORKFLOW 2: TECNICI INFORMATICI
    # ==========================================
    elif st.session_state.ruolo_utente == "magazziniere" and st.session_state.magazzino_selezionato == "Tecnici Informatici":
        st.markdown("<h2>💻 Dashboard Preparation Tecnici Informatici</h2>", unsafe_allow_html=True)
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
                        st.success("Stato aggiornato! Email di pronto ritiro inviata all'utente.")
                        st.rerun()

    # ==========================================
    # WORKFLOW 3: ADMIN
    # ==========================================
    elif st.session_state.ruolo_utente == "admin":
        with st.sidebar:
            st.markdown("### 👑 Pannello Amministrazione")
            sezione_selezionata = st.radio(
                "Seleziona area di lavoro:",
                [
                    "📦 Giacenza dei Magazzini",
                    "📋 Richieste Personale ATA",
                    "🔄 Gestione Comodati d'Uso",
                    "📊 Gestione Preventivi e Fornitori"
                ]
            )
            st.divider()

        # --- SEZIONE 1: GIACENZA DEI MAGAZZINI ---
        if sezione_selezionata == "📦 Giacenza dei Magazzini":
            st.markdown("## 📊 Stato Giacenze Inventario d'Istituto")
            tab_mag1, tab_mag2, tab_mag3 = st.tabs(["🏬 Magazzino 1 (ATA)", "🔧 Magazzino 2 (Officina)", "💻 Magazzino 3 (Informatica)"])
            with tab_mag1:
                st.dataframe(scarica_da_sheet("Inventario ata"), use_container_width=True, hide_index=True)
            with tab_mag2:
                st.dataframe(scarica_da_sheet("Inventario officina"), use_container_width=True, hide_index=True)
            with tab_mag3:
                st.dataframe(scarica_da_sheet("Inventario informatica"), use_container_width=True, hide_index=True)
            st.markdown("---")
            st.markdown("### 📋 Registro Generale Richieste Ricevute")
            st.dataframe(df_istanze, use_container_width=True, hide_index=True)

        # --- SEZIONE 2: RICHIESTE PERSONALE ATA ---
        elif sezione_selezionata == "📋 Richieste Personale ATA":
            st.markdown("## 📑 Istanze e Richieste Materiale Personale ATA")
            df_ata = df_istanze[df_istanze["ruolo_richiedente"].isin(["Personale ATA", "Collaboratore Scolastico"])] if not df_istanze.empty else pd.DataFrame()
            if df_ata.empty: st.info("Nessuna richiesta specifica inserita dal Personale ATA.")
            else: st.dataframe(df_ata, use_container_width=True, hide_index=True)

        # --- SEZIONE 3: GESTIONE COMODATI D'USO ---
        elif sezione_selezionata == "🔄 Gestione Comodati d'Uso":
            st.markdown("## 🛡️ Gestione Assegnazione e Riconsegna Comodati")
            tab_pronte, tab_riconsegna, tab_tutti_comodati, tab_registro_completo = st.tabs(["📦 PRATICHE PRONTE PER CONSEGNA", "🔄 RICONSEGNA BENI", "📋 INVENTARIO COMODATI", "📜 REGISTRO STORICO"])
            
            with tab_pronte:
                pronte = df_istanze[df_istanze["stato"] == "Lavorata"] if not df_istanze.empty else pd.DataFrame()
                if pronte.empty: st.info("Nessun materiale o dispositivo in attesa di consegna fisica.")
                else:
                    for _, riga in pronte.iterrows():
                        with st.expander(f"📦 ID {riga['id_richiesta']} - Consegna a {riga['richiedente']} [{riga['categoria_bene']}]"):
                            df_inv_c = scarica_da_sheet("Inventario_Comodati")
                            disp = df_inv_c[df_inv_c["stato"] == "Disponibile"]["id_bene"].tolist() if not df_inv_c.empty else []
                            col1, col2 = st.columns(2)
                            with col1:
                                if riga['categoria_bene'] in ["PC Notebook", "Chiave d'Accesso"]: bene_assegnato = st.selectbox("Seleziona seriale fisico da assegnare:", disp, key=f"b_{riga['id_richiesta']}")
                                else: bene_assegnato = st.text_input("Lotto / Quantità materiale consegnato:", value="1 Conf.", key=f"b_{riga['id_richiesta']}")
                            with col2:
                                metodo_firma = st.radio("Scegli come apporre la firma:", ["✍️ Disegna Firma Digitale", "🖼️ Carica immagine"], key=f"metodo_{riga['id_richiesta']}")
                                firma_base64_finale = ""
                                if metodo_firma == "✍️ Disegna Firma Digitale":
                                    mostra_pad_firma(riga['id_richiesta'])
                                    stringa_incollata = st.text_area("Incolla qui il codice firma generato:", value="", key=f"f_text_{riga['id_richiesta']}")
                                    if stringa_incollata.startswith("data:image/png;base64,"): firma_base64_finale = stringa_incollata
                                else:
                                    file_firma = st.file_uploader("Carica immagine firma:", type=["png", "jpg", "jpeg"], key=f"f_file_{riga['id_richiesta']}")
                                    if file_firma is not None: firma_base64_finale = "data:image/png;base64," + base64.b64encode(file_firma.read()).decode("utf-8")
                            
                            if st.button(f"Completa Consegna e Genera Verbale ## {riga['id_richiesta']}", type="primary"):
                                if (riga['categoria_bene'] not in ["PC Notebook", "Chiave d'Accesso"] or firma_base64_finale) and bene_assegnato:
                                    df_reg_c = scarica_da_sheet("Registro_Comodati")
                                    id_comodato_numerico = pd.to_numeric(df_reg_c["id_comodato"], errors='coerce')
                                    id_com = int(id_comodato_numerico.max()) + 1 if not df_reg_c.empty and not id_comodato_numerico.dropna().empty else 1001
                                    data_ora = datetime.now().strftime("%d/%m/%Y %H:%M")
                                    pdf_bytes = genera_pdf_comodato(id_com, riga['richiedente'], riga['ruolo_richiedente'], bene_assegnato, data_ora, "Consegna", firma_base64_finale, st.session_state.utente_corrente)
                                    
                                    if carica_su_drive_unico(pdf_bytes, f"Verbale_Consegna_{id_com}_{riga['richiedente']}.pdf", "application/pdf", ID_CARTELLA_CONSEGNE):
                                        idx = df_istanze.index[df_istanze["id_richiesta"].astype(str) == str(riga['id_richiesta'])].tolist()[0]
                                        df_istanze.at[idx, "stato"] = "Assegnata"
                                        carica_su_sheet(df_istanze, "Richieste_Preside")
                                        nuovo_c = pd.DataFrame([{"id_comodato": id_com, "tipo_soggetto": riga['ruolo_richiedente'], "nominativo": riga['richiedente'], "id_bene": bene_assegnato, "data_consegna": data_ora, "stato_comodato": "Chiuso/Consegnato"}])
                                        carica_su_sheet(pd.concat([df_reg_c, nuovo_c], ignore_index=True), "Registro_Comodati")
                                        if riga['categoria_bene'] in ["PC Notebook", "Chiave d'Accesso"]:
                                            df_inv_c.loc[df_inv_c["id_bene"] == bene_assegnato, "stato"] = "Assegnato"
                                            carica_su_sheet(df_inv_c, "Inventario_Comodati")
                                        st.success("Pratica Evasa! Verbale archiviato con successo.")
                                        st.rerun()

            with tab_riconsegna:
                df_reg_r = scarica_da_sheet("Registro_Comodati")
                comodati_attivi = df_reg_r[df_reg_r["stato_comodato"] == "Chiuso/Consegnato"] if not df_reg_r.empty else pd.DataFrame()
                if comodati_attivi.empty: st.info("Nessun bene risulta attualmente in comodato.")
                else:
                    for _, comodato in comodati_attivi.iterrows():
                        with st.expander(f"🔄 Comodato ID {comodato['id_comodato']} - {comodato['nominativo']} (Bene: {comodato['id_bene']})"):
                            col1_r, col2_r = st.columns(2)
                            with col1_r:
                                nota_ritiro = st.text_input("Note sullo stato al rientro:", value="Bene restituito integro", key=f"nota_reso_{comodato['id_comodato']}")
                                email_notifica_reso = st.text_input("Email copia verbale (Opzionale):", key=f"email_reso_{comodato['id_comodato']}")
                            with col2_r:
                                metodo_firma_r = st.radio("Metodo firma:", ["✍️ Disegna", "🖼️ Carica"], key=f"met_reso_{comodato['id_comodato']}")
                                firma_base64_reso = ""
                                if metodo_firma_r == "✍️ Disegna":
                                    mostra_pad_firma(f"reso_{comodato['id_comodato']}")
                                    stringa_incollata_r = st.text_area("Incolla codice firma reso:", key=f"txt_reso_{comodato['id_comodato']}")
                                    if stringa_incollata_r.startswith("data:image/png;base64,"): firma_base64_reso = stringa_incollata_r
                                else:
                                    file_firma_r = st.file_uploader("Carica immagine firma:", type=["png", "jpg"], key=f"file_reso_{comodato['id_comodato']}")
                                    if file_firma_r is not None: firma_base64_reso = "data:image/png;base64," + base64.b64encode(file_firma_r.read()).decode("utf-8")
                            
                            if st.button(f"Prendi in Carico e Genera Reso ## {comodato['id_comodato']}", type="primary"):
                                if firma_base64_reso:
                                    data_ora_reso = datetime.now().strftime("%d/%m/%Y %H:%M")
                                    pdf_bytes_r = genera_pdf_comodato(comodato['id_comodato'], comodato['nominativo'], comodato['tipo_soggetto'], comodato['id_bene'], data_ora_reso, "Riconsegna", firma_base64_reso, st.session_state.utente_corrente)
                                    if carica_su_drive_unico(pdf_bytes_r, f"Verbale_Riconsegna_{comodato['id_comodato']}_{comodato['nominativo']}.pdf", "application/pdf", ID_CARTELLA_RICONSEGNE):
                                        if email_notifica_reso.strip():
                                            invia_email_sistema(email_notifica_reso.strip(), f"Ricevuta di Riconsegna Bene - ID {comodato['id_comodato']}", f"<p>Bene {comodato['id_bene']} riconsegnato con successo in data {data_ora_reso}. Stato: {nota_ritiro}</p>")
                                        idx_reg = df_reg_r.index[df_reg_r["id_comodato"].astype(str) == str(comodato['id_comodato'])].tolist()[0]
                                        df_reg_r.at[idx_reg, "stato_comodato"] = "Reso/Concluso"
                                        carica_su_sheet(df_reg_r, "Registro_Comodati")
                                        df_inv_r = scarica_da_sheet("Inventario_Comodati")
                                        if not df_inv_r.empty and comodato['id_bene'] in df_inv_r["id_bene"].values.tolist():
                                            df_inv_r.loc[df_inv_r["id_bene"] == comodato['id_bene'], "stato"] = "Disponibile"
                                            carica_su_sheet(df_inv_r, "Inventario_Comodati")
                                        st.success("Riconsegna completata con successo!")
                                        st.rerun()
                                else:
                                    st.error("Inserire la firma digitale per validare il rientro del bene.")

            with tab_tutti_comodati: st.dataframe(scarica_da_sheet("Inventario_Comodati"), use_container_width=True, hide_index=True)
            with tab_registro_completo: st.dataframe(df_istanze, use_container_width=True, hide_index=True)

        # --- SEZIONE 4: GESTIONE PREVENTIVI INTEGRATA ---
        elif sezione_selezionata == "📊 Gestione Preventivi e Fornitori":
            if MODULO_PREVENTIVI_DISPONIBILE:
                try:
                    mostra_interfaccia_preventivi(
                        scarica_da_sheet, 
                        carica_su_sheet, 
                        invia_email_sistema, 
                        URL_INTERMEDIARIO_SILENZIOSO, 
                        df_istanze
                    )
                except Exception as e:
                    st.error(f"❌ Errore durante l'esecuzione del modulo preventivi: {e}")
                    st.info("Verifica che il file `gestione_preventivi.py` sia aggiornato alla struttura corretta.")
            else:
                st.info("ℹ️ Il modulo preventivi è configurato, ma il file `gestione_preventivi.py` non è ancora stato creato o caricato nella cartella.")

    # ==========================================
    # WORKFLOW 4: ALTRI MAGAZZINI (ATA O STANDARD)
    # ==========================================
    elif st.session_state.ruolo_utente == "magazziniere":
        st.markdown(f"## 📦 Magazzino Standard: {st.session_state.magazzino_selezionato}")
        st.dataframe(scarica_da_sheet(MAPPA_SCHEDE[st.session_state.magazzino_selezionato]["inventario"]), use_container_width=True, hide_index=True)
