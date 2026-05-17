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

# --- IMPORTAZIONE SICURA E DINAMICA DEL MODULO PREVENTIVI ---
# Evita il crash dell'intera applicazione se il file secondario è in fase di caricamento
try:
    import gestione_preventivi
    import importlib
    importlib.reload(gestione_preventivi)
    mostra_interfaccia_preventivi = gestione_preventivi.mostra_interfaccia_preventivi
    MODULO_PREVENTIVI_DISPONIBILE = True
except Exception as e:
    MODULO_PREVENTIVI_DISPONIBILE = False

# --- CONFIGURAZIONI SISTEMA ---
URL_INTERMEDIARIO_SILENZIOSO = "https://script.google.com/macros/s/AKfycbyXBLjDpJrSGHoUpuspTsNAG9f6lGhF1e8oGyJ8nkY6jZMTJo04zsT_6eLyEybGgv4/exec"
ID_CARTELLA_CONSEGNE = "1pJpYtIfcMEKFh62rSOGTXWYG8CgvzN4m"
ID_CARTELLA_RICONSEGNE = "1S6IcauDOc-8sFiCdGv67CHKf_H9u7BVW"
SPREADSHEET_ID = "1Q91H_TULvpsnPcyOwQ1lxmjOf809xp4cUz9p1EdMc-4"
ID_CARTELLA_DRIVE_PRINCIPALE = "1bVTs2smvVJONs2oIAFZdDvX9pYDK9MZT"
URL_LOGO = "https://cspace.spaggiari.eu//pub/TVII0004/TVII0004-intestazione-nuova-senzaloghi.png?_t=1712923868"
EMAIL_PRESIDE_TEST = "marcobrunetti14@gmail.com"

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

# --- CONTROLLO LIBRERIE COMODATI E PDF ---
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

st.set_page_config(page_title="Gestione Magazzini Scarpa", page_icon="🏢", layout="wide")

# --- STILI PREMIUM ---
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

# --- FUNZIONI DI CONNESSIONE E SCARICAMENTO DATA ---
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
    html_ut = f"<h3>Portale Logistico Scarpa</h3><p>Gentile {utente} ({ruolo}), la tua richiesta <b>ID {id_req}</b> è registrata.</p>"
    invia_email_sistema(email_ut, f"Richiesta ID {id_req} in lavorazione", html_ut)
    url_approva = f"https://magazzino-scarpa.streamlit.app/?action=approve&id={id_req}"
    url_rifiuta = f"https://magazzino-scarpa.streamlit.app/?action=reject&id={id_req}"
    html_pr = f"""<h2>Nuova Istanza da Autorizzare</h2><p><b>Richiedente:</b> {utente} ({ruolo})<br><b>Oggetto:</b> {ogg}<br><b>Motivazione:</b> {mot}</p>
    <div style='margin-top:20px;'><a href='{url_approva}' style='background:#16a34a;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;margin-right:10px;'>🟢 AUTORIZZA</a></div>"""
    invia_email_sistema(EMAIL_PRESIDE_TEST, f"📦 NUOVA ISTANZA - ID {id_req}", html_pr)

# --- COMPONENTE PDF MINISTERIALE COMODATI ---
class PDFMinisteriale(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "", 7)
        footer_text = 'ISISS "A. SCARPA"     Via Primo Maggio, 3 31045 Motta di Livenza (Tv)      C.F. 94071460268'
        self.cell(180, 4, pulisci_caratteri_fpdf(footer_text), ln=True, align="C")

def pulisci_caratteri_fpdf(testo):
    mappa = { "à": "a'", "è": "e'", "é": "e'", "ì": "i'", "ò": "o'", "ù": "u'" }
    for k, v in mappa.items(): testo = testo.replace(k, v)
    return testo.encode('raw_unicode_escape').decode('utf-8').encode('latin1', 'replace').decode('latin1')

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
    
    pdf.set_font("Times", "", 11)
    pdf.cell(110, 5, "", ln=False)
    pdf.cell(70, 5, pulisci_caratteri_fpdf(f"{nome} ({ruolo})"), ln=True, align="L")
    pdf.ln(10)
    
    pdf.set_font("Times", "B", 11)
    pdf.cell(24, 5, "OGGETTO: ", ln=False)
    pdf.multi_cell(156, 5, pulisci_caratteri_fpdf(f"Verbale di {tipo_operazione} Bene in Comodato d'Uso - ID {id_contratto}"))
    pdf.ln(12)
    
    corpo = f"Si attesta la formale operazione di {tipo_operazione} del bene {bene} intestato a {nome} in data {data}."
    pdf.set_font("Times", "", 11)
    pdf.multi_cell(180, 6, pulisci_caratteri_fpdf(corpo))
    
    pdf.set_y(-55)
    y_f = pdf.get_y()
    pdf.cell(100, 5, pulisci_caratteri_fpdf(f"F.to l'Amministratore ({utente_loggato})"))
    
    if firma_base64 and len(firma_base64) > 100:
        try:
            dati_f = firma_base64.split(",")[1] if "," in firma_base64 else firma_base64
            img_data = base64.b64decode(dati_f)
            pdf.image(io.BytesIO(img_data), x=120, y=y_f + 5, w=45)
        except Exception: pdf.text(120, y_f + 10, "[Firma Acquisita]")
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
    except Exception: return None

def mostra_pad_firma(chiave_id):
    html_pad = f"""
    <div style="background: #f8fafc; border: 2px dashed #cbd5e1; padding: 10px; border-radius: 12px; font-family: sans-serif;">
        <canvas id="canvas_{chiave_id}" width="420" height="120" style="border:2px solid #64748b; background:#ffffff; border-radius:8px; cursor:crosshair; touch-action:none;"></canvas>
        <div style="margin-top:8px;">
            <button type="button" onclick="p_clear_{chiave_id}()" style="padding:5px 10px; background:#ef4444; color:white; border:none; border-radius:4px; cursor:pointer;">Cancella</button>
            <button type="button" onclick="p_gen_{chiave_id}()" style="padding:5px 10px; background:#22c55e; color:white; border:none; border-radius:4px; cursor:pointer;">Conferma Firma</button>
        </div>
        <textarea id="out_{chiave_id}" style="width:100%; height:40px; margin-top:8px; display:none;" readonly></textarea>
        <p id="msg_{chiave_id}" style="font-size:11px; color:#b91c1c; font-weight:bold; display:none;">Firma Codificata! Fai TRIPLO CLICK nel box sopra, COPIA il testo e incollalo nel campo Streamlit.</p>
    </div>
    <script>
        var canvas = document.getElementById('canvas_{chiave_id}'); var ctx = canvas.getContext('2d');
        ctx.strokeStyle = '#000000'; ctx.lineWidth = 3; ctx.lineCap = 'round'; var drawing = false;
        function getPos(e) {{ var r = canvas.getBoundingClientRect(); if(e.touches) return {{x: e.touches[0].clientX - r.left, y: e.touches[0].clientY - r.top}}; return {{x: e.clientX - r.left, y: e.clientY - r.top}}; }}
        canvas.addEventListener('mousedown', function(e){{ drawing = true; var p = getPos(e); ctx.beginPath(); ctx.moveTo(p.x, p.y); }});
        canvas.addEventListener('mousemove', function(e){{ if(!drawing) return; var p = getPos(e); ctx.lineTo(p.x, p.y); ctx.stroke(); }});
        canvas.addEventListener('mouseup', function(){{ drawing = false; }});
        canvas.addEventListener('touchstart', function(e){{ drawing = true; var p = getPos(e); ctx.beginPath(); ctx.moveTo(p.x, p.y); e.preventDefault(); }});
        canvas.addEventListener('touchmove', function(e){{ if(!drawing) return; var p = getPos(e); ctx.lineTo(p.x, p.y); ctx.stroke(); e.preventDefault(); }});
        canvas.addEventListener('touchend', function(){{ drawing = false; }});
        function p_clear_{chiave_id}() {{ ctx.clearRect(0, 0, canvas.width, canvas.height); document.getElementById('out_{chiave_id}').style.display='none'; document.getElementById('msg_{chiave_id}').style.display='none'; }}
        function p_gen_{chiave_id}() {{ var url = canvas.toDataURL(); var t = document.getElementById('out_{chiave_id}'); t.value = url; t.style.display='block'; document.getElementById('msg_{chiave_id}').style.display='block'; t.select(); }}
    </script>
    """
    st.components.v1.html(html_pad, height=220)

# --- LOGICA QUERY PARAMS ---
query_params = st.query_params
if "action" in query_params and "id" in query_params:
    df_f = scarica_da_sheet("Richieste_Preside")
    if not df_f.empty:
        idx_l = df_f.index[df_f["id_richiesta"].astype(str) == str(query_params["id"])].tolist()
        if idx_l:
            df_f.at[idx_l[0], "stato"] = "Lavorata" if query_params["action"] == "approve" else "Rifiutata"
            carica_su_sheet(df_f, "Richieste_Preside")
            st.success("Stato aggiornato via mail!")
    st.stop()

# --- INITIALIZE USER STATE ---
if "ruolo_utente" not in st.session_state: st.session_state.ruolo_utente = None
if "utente_corrente" not in st.session_state: st.session_state.utente_corrente = ""
if "ruolo_specifico" not in st.session_state: st.session_state.ruolo_specifico = ""
if "magazzino_selezionato" not in st.session_state: st.session_state.magazzino_selezionato = None

if st.session_state.ruolo_utente is None:
    col_l, col_c, col_r = st.columns([1, 1.8, 1])
    with col_c:
        st.markdown("<h2 style='text-align: center;'>Piattaforma Logistica Scarpa</h2>", unsafe_allow_html=True)
        with st.container(border=True):
            scelta = st.radio("Seleziona profilo d'accesso:", ["📝 Utente Esterno / Richiedente", "🔑 Personale di Magazzino / Amministrazione"])
            if "Utente" in scelta:
                nome = st.text_input("Nome e Cognome:")
                ruolo = st.selectbox("Ruolo:", ["Docente", "Alunno", "Personale ATA"])
                em = st.text_input("Email istituzionale:")
                if st.button("Accedi al Modulo", type="primary", use_container_width=True):
                    if nome.strip() and em.strip():
                        st.session_state.ruolo_utente = "collaboratore"
                        st.session_state.utente_corrente = nome.strip()
                        st.session_state.ruolo_specifico = ruolo
                        st.session_state.email_utente = em.strip()
                        st.rerun()
            else:
                pwd = st.text_input("Codice di accesso:", type="password")
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
    col_t, col_l = st.columns([4, 1])
    with col_t: st.markdown(f"Connesso come: **{st.session_state.utente_corrente.upper()}**")
    with col_l:
        if st.button("🚪 Esci", use_container_width=True):
            st.session_state.ruolo_utente = None
            st.rerun()
    st.image(URL_LOGO, use_container_width=True)

    df_istanze = scarica_da_sheet("Richieste_Preside")

    # ==========================================
    # INTERFACCIA COLLABORATORE (RICHIESTE)
    # ==========================================
    if st.session_state.ruolo_utente == "collaboratore":
        st.markdown("### 📝 Compila una nuova richiesta logistica")
        with st.form("form_richiede"):
            cat = st.selectbox("Categoria Bene:", ["PC Notebook", "Cancelleria", "Materiale Logistico"])
            obj = st.text_input("Oggetto:")
            mot = st.text_area("Motivazione:")
            if st.form_submit_button("Invia Richiesta alla Presidenza", use_container_width=True):
                if obj.strip() and mot.strip():
                    id_r = int(pd.to_numeric(df_istanze["id_richiesta"], errors='coerce').max()) + 1 if not df_istanze.empty else 101
                    nuovo = pd.DataFrame([{"id_richiesta": id_r, "data_richiesta": datetime.now().strftime("%d/%m/%Y %H:%M"), "richiedente": st.session_state.utente_corrente, "ruolo_richiedente": st.session_state.ruolo_specifico, "email_utente": st.session_state.email_utente, "tipo_istanza": "Standard", "categoria_bene": cat, "oggetto": obj.strip(), "motivazione": mot.strip(), "stato": "In attesa di approvazione"}])
                    carica_su_sheet(pd.concat([df_istanze, nuovo], ignore_index=True), "Richieste_Preside")
                    invia_notifica_nuova_richiesta(id_r, st.session_state.utente_corrente, st.session_state.ruolo_specifico, st.session_state.email_utente, "Standard", obj.strip(), mot.strip())
                    st.success("Richiesta registrata e notificata!")

    # ==========================================
    # INTERFACCIA AMMINISTRATORE (ADMIN / UFF TECNICO)
    # ==========================================
    elif st.session_state.ruolo_utente == "admin":
        with st.sidebar:
            st.markdown("### 👑 Amministrazione")
            sez = st.sidebar.radio("Seleziona Area:", ["Giacenze", "Comodati", "📊 Gestione Preventivi e Fornitori"])
            
        if sez == "Giacenze":
            st.markdown("## 📊 Stato Inventari")
            st.dataframe(df_istanze, use_container_width=True, hide_index=True)
            
        elif sez == "Comodati":
            st.markdown("## 🛡️ Gestione Verbali ed Assegnazioni")
            tab_c, tab_r = st.tabs(["📦 Consegna Beni", "🔄 Riconsegna Resi"])
            with tab_c:
                pronte = df_istanze[df_istanze["stato"] == "Lavorata"] if not df_istanze.empty else pd.DataFrame()
                if pronte.empty: st.info("Nessun bene pronto per il rilascio.")
                else:
                    for _, riga in pronte.iterrows():
                        with st.expander(f"Assegna a {riga['richiedente']}"):
                            seriale = st.text_input("Inserisci ID/Seriale Bene:", key=f"s_{riga['id_richiesta']}")
                            firma_code = st.text_area("Codice Firma:", key=f"f_{riga['id_richiesta']}")
                            mostra_pad_firma(riga['id_richiesta'])
                            if st.button("Sottoscrivi Verbale Consegna", key=f"b_{riga['id_richiesta']}"):
                                pdf = genera_pdf_comodato(riga['id_richiesta'], riga['richiedente'], riga['ruolo_richiedente'], seriale, datetime.now().strftime("%d/%m/%Y"), "Consegna", firma_code)
                                carica_su_drive_unico(pdf, f"Consegna_{riga['id_richiesta']}.pdf", "application/pdf", ID_CARTELLA_CONSEGNE)
                                st.success("Documento firmato e caricato su Google Drive!")
                                
        elif sez == "📊 Gestione Preventivi e Fornitori":
            if MODULO_PREVENTIVI_DISPONIBILE:
                mostra_interfaccia_preventivi(scarica_da_sheet, carica_su_sheet, invia_email_sistema, URL_INTERMEDIARIO_SILENZIOSO, df_istanze)
            else:
                st.info("ℹ️ Il modulo preventivi è configurato, ma il file `gestione_preventivi.py` non è ancora stato creato o caricato correttamente nella cartella.")

    # ==========================================
    # INTERFACCIA OPERATORI MAGAZZINO (ATA / OFFICINA / INFO)
    # ==========================================
    elif st.session_state.ruolo_utente == "magazziniere":
        st.markdown(f"## 🏬 Pannello Magazzino: {st.session_state.magazzino_selezionato}")
        t1, t2 = st.tabs(["📋 Inventario Corrente", "➕ Segnala Fabbisogno / Mancanti"])
        
        with t1:
            st.dataframe(scarica_da_sheet(MAPPA_SCHEDE[st.session_state.magazzino_selezionato]["inventario"]), use_container_width=True, hide_index=True)
            
        with t2:
            st.markdown("### Segnala rotture di stock o materiale da acquistare")
            with st.form("form_fabb"):
                mat = st.text_input("Descrizione dettagliata materiale:")
                qta = st.text_input("Quantità / Confezioni stimate:")
                note = st.text_area("Note aggiuntive:")
                if st.form_submit_button("Invia a Ufficio Tecnico"):
                    if mat.strip():
                        df_rm = scarica_da_sheet("Richieste_Preventivo_Magazzino")
                        id_rm = 2001 if df_rm.empty else int(pd.to_numeric(df_rm["id_richiesta_mag"], errors='coerce').max()) + 1
                        nuovo = pd.DataFrame([{"id_richiesta_mag": id_rm, "data_creazione": datetime.now().strftime("%d/%m/%Y %H:%M"), "magazzino_origine": st.session_state.magazzino_selezionato, "materiale_richiesto": mat.strip(), "quantita_esimata": qta.strip(), "stato_iter": "In attesa di preventivi", "note": note.strip()}])
                        carica_su_sheet(pd.concat([df_rm, nuovo], ignore_index=True), "Richieste_Preventivo_Magazzino")
                        st.success(f"Richiesta registrata con successo (ID REQ: {id_rm})!")
                    else:
                        st.error("Specificare il materiale.")
