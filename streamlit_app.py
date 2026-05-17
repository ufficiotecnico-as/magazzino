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

# --- IMPORTAZIONE SICURA DEL NUOVO MODULO INDEPENDENTE ---
try:
    from gestione_preventivi import mostra_interfaccia_preventivi
    MODULO_PREVENTIVI_DISPONIBILE = True
except Exception:
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

# --- CONTROLLO LIBRERIE ---
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

# --- STILI ---
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

# --- GOOGLE CONNECTIONS ---
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
    html_ut = f"<h3>Portale Logistico Scarpa</h3><p>Gentile {utente} ({ruolo}), la tua richiesta <b>ID {id_req}</b> per '{ogg}' è in fase di valutazione.</p>"
    invia_email_sistema(email_ut, f"Richiesta ID {id_req} in lavorazione", html_ut)
    url_approva = f"https://magazzino-scarpa.streamlit.app/?action=approve&id={id_req}"
    url_rifiuta = f"https://magazzino-scarpa.streamlit.app/?action=reject&id={id_req}"
    html_pr = f"""<h2>Nuova Istanza da Autorizzare</h2><p><b>Richiedente:</b> {utente} ({ruolo})<br><b>Oggetto:</b> {ogg}<br><b>Motivazione:</b> {mot}</p>
    <div style='margin-top:20px;'><a href='{url_approva}' style='background:#16a34a;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;margin-right:10px;'>🟢 AUTORIZZA ADESSO</a><a href='{url_rifiuta}' style='background:#dc2626;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;'>🔴 RIFIUTA</a></div>"""
    invia_email_sistema(EMAIL_PRESIDE_TEST, f"📦 NUOVA ISTANZA DA VALUTARE - ID {id_req}", html_pr)

def invia_notifica_approvata_preside(id_req, email_ut, ogg, categoria_bene):
    dest = "passata ai Tecnici Informatici per configurazione." if categoria_bene == "PC Notebook" else "trasmessa direttamente all'Ufficio Tecnico/Magazzino."
    html = f"<h3>Richiesta Approvata!</h3><p>La tua richiesta <b>ID {id_req}</b> per '{ogg}' è stata autorizzata ed è {dest}</p>"
    invia_email_sistema(email_ut, f"Richiesta ID {id_req} Autorizzata dalla Dirigente", html)

def invia_notifica_pronto_ritiro(id_req, email_ut, ogg):
    html = f"<h3>Pronto per il ritiro!</h3><p>Il materiale relativo alla tua richiesta <b>ID {id_req} ({ogg})</b> è pronto al magazzino.</p>"
    invia_email_sistema(email_ut, f"Materiale pronto per il ritiro - ID {id_req}", html)

# --- COMPONENTE PDF MINISTERIALE ---
class PDFMinisteriale(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "", 7)
        self.set_text_color(100, 100, 100)
        footer_text = 'ISISS "A. SCARPA"     Via Primo Maggio, 3 31045 Motta di Livenza (Tv)      C.F. 94071460268      Codice univoco UFOA6X'
        self.cell(180, 4, pulisci_caratteri_fpdf(footer_text), ln=True, align="C")

def pulisci_caratteri_fpdf(testo):
    mappa = { "à": "a'", "á": "a'", "è": "e'", "é": "e'", "ì": "i'", "ò": "o'", "ù": "u'" }
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
                 f"con la massima cura e la dovuta diligenza professionale.")
    else:
        corpo = (f"Con la presente si attesta la formale riconsegna e il CONSEQUENTE rientro al magazzino del bene "
                 f"d'Istituto (Identificativo Bene: {bene}) precedentemente concesso in comodato d'uso "
                 f"a {nome}.")
                 
    pdf.multi_cell(180, 6, pulisci_caratteri_fpdf(corpo))
    pdf.ln(20)
    
    pdf.set_font("Times", "", 12)
    pdf.cell(180, 5, pulisci_caratteri_fpdf("La Dirigente Scolastica"), ln=True, align="C")
    pdf.set_font("Times", "B", 12)
    pdf.cell(180, 5, pulisci_caratteri_fpdf("Maria Cristina Taddeo"), ln=True, align="C")
    
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
        except Exception: pdf.text(115, y_f + 10, "[Firma Acquisita]")
    else:
        pdf.text(115, y_f + 10, "____________________________")
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

# --- REINDIRIZZAMENTO RAPIDO PARAMETRI ---
query_params = st.query_params
if "action" in query_params and "id" in query_params:
    azione = query_params["action"]
    id_req = query_params["id"]
    df_f = scarica_da_sheet("Richieste_Preside")
    if not df_f.empty and "id_richiesta" in df_f.columns:
        df_f["id_richiesta"] = df_f["id_richiesta"].astype(str)
        idx_lista = df_f.index[df_f["id_richiesta"] == str(id_req)].tolist()
        if idx_lista:
            idx = idx_lista[0]
            nuovo_stato = "In lavorazione" if (azione == "approve" and df_f.at[idx, "categoria_bene"] == "PC Notebook") else ("Lavorata" if azione == "approve" else "Rifiutata")
            df_f.at[idx, "stato"] = nuovo_stato
            carica_su_sheet(df_f, "Richieste_Preside")
            if azione == "approve":
                invia_notifica_approvata_preside(id_req, df_f.at[idx, "email_utente"], df_f.at[idx, "oggetto"], df_f.at[idx, "categoria_bene"])
                if df_f.at[idx, "categoria_bene"] != "PC Notebook":
                    invia_notifica_pronto_ritiro(id_req, df_f.at[idx, "email_utente"], df_f.at[idx, "oggetto"])
            st.success("Decisione registrata!")
    st.stop()

# --- INITIALIZE STATE ---
if "ruolo_utente" not in st.session_state: st.session_state.ruolo_utente = None
if "utente_corrente" not in st.session_state: st.session_state.utente_corrente = ""
if "ruolo_specifico" not in st.session_state: st.session_state.ruolo_specifico = ""
if "magazzino_selezionato" not in st.session_state: st.session_state.magazzino_selezionato = None

# --- PORTALE LOGIN ---
if st.session_state.ruolo_utente is None:
    col_l, col_c, col_r = st.columns([1, 1.8, 1])
    with col_c:
        st.markdown("<h2 style='text-align: center;'>Piattaforma Logistica di Istituto</h2>", unsafe_allow_html=True)
        with st.container(border=True):
            scelta = st.radio("Seleziona profilo d'accesso:", ["📝 Collaboratore / Alunno / Docente (Invia Richiesta)", "🔑 Staff Magazzino / Amministrazione / Tecnici"])
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
                    else: st.error("Compila tutti i campi.")
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
                    else: st.error("Codice errato.")
else:
    col_t, col_b_logout = st.columns([4, 1])
    with col_t: st.markdown(f"Utente: **{st.session_state.utente_corrente.upper()}**")
    with col_b_logout:
        if st.button("🚪 Esci", use_container_width=True):
            st.session_state.ruolo_utente = None
            st.rerun()
    st.image(URL_LOGO, use_container_width=True)

    df_istanze = scarica_da_sheet("Richieste_Preside")

    # ==========================================
    # WORKFLOW INTERNO: COLLABORATORE RAGAZZI
    # ==========================================
    if st.session_state.ruolo_utente == "collaboratore":
        st.markdown(f"### Modulo Richieste Logistiche per: {st.session_state.ruolo_specifico}")
        categorie_disponibili = ["PC Notebook", "Chiave d'Accesso"] if st.session_state.ruolo_specifico in ["Alunno", "Docente"] else ["Cancelleria", "Carta e Consumabili", "Materiale d'Officina"]
        tipo_istanza_default = "Comodato d'Uso Dispositivo" if st.session_state.ruolo_specifico in ["Alunno", "Docente"] else "Materiale Logistico / Consumo"

        with st.form("mod_rich_divise"):
            cat_b = st.selectbox("Seleziona Bene richiesto:", categorie_disponibili)
            obj_b = st.text_input("Oggetto della Richiesta:")
            mot_b = st.text_area("Motivazione dettagliata per la Direzione:")
            if st.form_submit_button("Invia Istanza alla Dirigente", use_container_width=True):
                if obj_b.strip() and mot_b.strip():
                    id_r_num = pd.to_numeric(df_istanze["id_richiesta"], errors='coerce')
                    nuovo_id = int(id_r_num.max()) + 1 if not df_istanze.empty and not id_r_num.dropna().empty else 101
                    nuova_r = pd.DataFrame([{"id_richiesta": nuovo_id, "data_richiesta": datetime.now().strftime("%d/%m/%Y %H:%M"), "richiedente": st.session_state.utente_corrente, "ruolo_richiedente": st.session_state.ruolo_specifico, "email_utente": st.session_state.email_utente, "tipo_istanza": tipo_istanza_default, "categoria_bene": cat_b, "oggetto": obj_b.strip(), "motivazione": mot_b.strip(), "stato": "In attesa di approvazione"}])
                    carica_su_sheet(pd.concat([df_istanze, nuova_r], ignore_index=True), "Richieste_Preside")
                    invia_notifica_nuova_richiesta(nuovo_id, st.session_state.utente_corrente, st.session_state.ruolo_specifico, st.session_state.email_utente, tipo_istanza_default, obj_b.strip(), mot_b.strip())
                    st.success(f"Richiesta ID {nuovo_id} inoltrata alla Dirigente!")

    # ==========================================
    # WORKFLOW INTERNO: TECNICI INFORMATICI 
    # ==========================================
    elif st.session_state.ruolo_utente == "magazziniere" and st.session_state.magazzino_selezionato == "Tecnici Informatici":
        st.markdown("<h2>💻 Dashboard Laboratorio Hardware Informatico</h2>", unsafe_allow_html=True)
        tab_scorte_it, tab_lavorazione_it, tab_fabbisogno_it = st.tabs(["📋 Inventario Hardware", "🛠️ PC da Configurare", "➕ Segnala Fabbisogno"])
        
        with tab_scorte_it:
            st.dataframe(scarica_da_sheet("Inventario informatica"), use_container_width=True, hide_index=True)
            
        with tab_lavorazione_it:
            da_lavorare = df_istanze[(df_istanze["stato"] == "In lavorazione") & (df_istanze["categoria_bene"] == "PC Notebook")] if not df_istanze.empty else pd.DataFrame()
            if da_lavorare.empty: st.info("Nessun Notebook in attesa di configurazione software.")
            else:
                for _, riga in da_lavorare.iterrows():
                    with st.container(border=True):
                        st.markdown(f"🛠️ **Richiesta ID {riga['id_richiesta']}** | Destinatario: **{riga['richiedente']}**")
                        if st.button(f"Marca come PRONTO AL RITIRO ## ID {riga['id_richiesta']}", use_container_width=True):
                            idx = df_istanze.index[df_istanze["id_richiesta"].astype(str) == str(riga['id_richiesta'])].tolist()[0]
                            df_istanze.at[idx, "stato"] = "Lavorata"
                            carica_su_sheet(df_istanze, "Richieste_Preside")
                            invia_notifica_pronto_ritiro(riga['id_richiesta'], riga['email_utente'], riga['oggetto'])
                            st.success("Stato aggiornato!")
                            st.rerun()
                            
        with tab_fabbisogno_it:
            st.markdown("### Richiedi acquisto nuovo materiale informatico")
            with st.form("form_f_it"):
                mat_it = st.text_input("Materiale Informatico (es. 5 Monitor HDMI):")
                qta_it = st.text_input("Specifiche/Quantità:")
                note_it = st.text_area("Note:")
                if st.form_submit_button("Invia ad Ufficio Tecnico"):
                    df_rm = scarica_da_sheet("Richieste_Preventivo_Magazzino")
                    id_rm = 2001 if df_rm.empty else int(pd.to_numeric(df_rm["id_richiesta_mag"], errors='coerce').max()) + 1
                    nuovo = pd.DataFrame([{"id_richiesta_mag": id_rm, "data_creazione": datetime.now().strftime("%d/%m/%Y %H:%M"), "magazzino_origine": "Tecnici Informatici", "materiale_richiesto": mat_it, "quantita_esimata": qta_it, "stato_iter": "In attesa di preventivi", "note": note_it}])
                    carica_su_sheet(pd.concat([df_rm, nuovo], ignore_index=True), "Richieste_Preventivo_Magazzino")
                    st.success("Richiesta inserita nel registro preventivi admin!")

    # ==========================================
    # WORKFLOW INTERNO: AMMINISTRATORE (ADMIN / UFF TECNICO)
    # ==========================================
    elif st.session_state.ruolo_utente == "admin":
        with st.sidebar:
            st.markdown("### 👑 Amministrazione Globale")
            sezione_selezionata = st.radio("Seleziona area di lavoro:", ["📦 Giacenza dei Magazzini", "📋 Richieste Personale ATA", "🔄 Gestione Comodati d'Uso", "📊 Gestione Preventivi e Fornitori"])
        
        if sezione_selezionata == "📦 Giacenza dei Magazzini":
            st.markdown("## 📊 Stato Giacenze Inventario d'Istituto")
            tab_mag1, tab_mag2, tab_mag3 = st.tabs(["🏬 Magazzino 1 (ATA)", "🔧 Magazzino 2 (Officina)", "💻 Magazzino 3 (Informatica)"])
            with tab_mag1: st.dataframe(scarica_da_sheet("Inventario ata"), use_container_width=True, hide_index=True)
            with tab_mag2: st.dataframe(scarica_da_sheet("Inventario officina"), use_container_width=True, hide_index=True)
            with tab_mag3: st.dataframe(scarica_da_sheet("Inventario informatica"), use_container_width=True, hide_index=True)
            st.markdown("### 📋 Elenco Completo Istanze Personale/Alunni")
            st.dataframe(df_istanze, use_container_width=True, hide_index=True)

        elif sezione_selezionata == "📋 Richieste Personale ATA":
            st.markdown("## 📑 Richieste Interne Generali")
            st.dataframe(df_istanze, use_container_width=True, hide_index=True)

        elif sezione_selezionata == "🔄 Gestione Comodati d'Uso":
            st.markdown("## 🛡️ Gestione Assegnazione e Riconsegna Comodati")
            tab_pronte, tab_riconsegna, tab_tutti_comodati = st.tabs(["📦 PRATICHE DA CONSEGNARE", "🔄 RICONSEGNA BENI", "📋 INVENTARIO COMODATI"])
            
            with tab_pronte:
                pronte = df_istanze[df_istanze["stato"] == "Lavorata"] if not df_istanze.empty else pd.DataFrame()
                if pronte.empty: st.info("Nessuna pratica in attesa di consegna materiale.")
                else:
                    for _, riga in pronte.iterrows():
                        with st.expander(f"📦 Consegna a {riga['richiedente']} [{riga['categoria_bene']}]"):
                            df_inv_c = scarica_da_sheet("Inventario_Comodati")
                            disp = df_inv_c[df_inv_c["stato"] == "Disponibile"]["id_bene"].tolist() if not df_inv_c.empty else []
                            bene_assegnato = st.selectbox("Seleziona seriale:", disp, key=f"b_{riga['id_richiesta']}")
                            stringa_incollata = st.text_area("Codice Firma Digitale (Generato dal Pad):", key=f"f_text_{riga['id_richiesta']}")
                            mostra_pad_firma(riga['id_richiesta'])
                            
                            if st.button(f"Valida e Genera Verbale Consegna ## {riga['id_richiesta']}", type="primary"):
                                df_reg_c = scarica_da_sheet("Registro_Comodati")
                                id_com = int(pd.to_numeric(df_reg_c["id_comodato"], errors='coerce').max() + 1) if not df_reg_c.empty else 1001
                                data_ora = datetime.now().strftime("%d/%m/%Y %H:%M")
                                pdf_bytes = genera_pdf_comodato(id_com, riga['richiedente'], riga['ruolo_richiedente'], bene_assegnato, data_ora, "Consegna", stringa_incollata, st.session_state.utente_corrente)
                                if carica_su_drive_unico(pdf_bytes, f"Verbale_Consegna_{id_com}.pdf", "application/pdf", ID_CARTELLA_CONSEGNE):
                                    idx = df_istanze.index[df_istanze["id_richiesta"].astype(str) == str(riga['id_richiesta'])].tolist()[0]
                                    df_istanze.at[idx, "stato"] = "Assegnata"
                                    carica_su_sheet(df_istanze, "Richieste_Preside")
                                    nuovo_c = pd.DataFrame([{"id_comodato": id_com, "tipo_soggetto": riga['ruolo_richiedente'], "nominativo": riga['richiedente'], "id_bene": bene_assegnato, "data_consegna": data_ora, "stato_comodato": "Chiuso/Consegnato"}])
                                    carica_su_sheet(pd.concat([df_reg_c, nuovo_c], ignore_index=True), "Registro_Comodati")
                                    df_inv_c.loc[df_inv_c["id_bene"] == bene_assegnato, "stato"] = "Assegnato"
                                    carica_su_sheet(df_inv_c, "Inventario_Comodati")
                                    st.success("Verbale creato e archiviato!"); st.rerun()

            with tab_riconsegna:
                df_reg_r = scarica_da_sheet("Registro_Comodati")
                comodati_attivi = df_reg_r[df_reg_r["stato_comodato"] == "Chiuso/Consegnato"] if not df_reg_r.empty else pd.DataFrame()
                if comodati_attivi.empty: st.info("Nessun prestito attivo.")
                else:
                    for _, comodato in comodati_attivi.iterrows():
                        with st.expander(f"🔄 Riconsegna ID {comodato['id_comodato']} - {comodato['nominativo']}"):
                            stringa_incollata_r = st.text_area("Codice Firma Reso:", key=f"txt_reso_{comodato['id_comodato']}")
                            mostra_pad_firma(f"reso_{comodato['id_comodato']}")
                            if st.button(f"Prendi in Carico Reso ## {comodato['id_comodato']}"):
                                data_ora_reso = datetime.now().strftime("%d/%m/%Y %H:%M")
                                pdf_bytes_r = genera_pdf_comodato(comodato['id_comodato'], comodato['nominativo'], comodato['tipo_soggetto'], comodato['id_bene'], data_ora_reso, "Riconsegna", stringa_incollata_r, st.session_state.utente_corrente)
                                if carica_su_drive_unico(pdf_bytes_r, f"Verbale_Riconsegna_{comodato['id_comodato']}.pdf", "application/pdf", ID_CARTELLA_RICONSEGNE):
                                    idx_reg = df_reg_r.index[df_reg_r["id_comodato"].astype(str) == str(comodato['id_comodato'])].tolist()[0]
                                    df_reg_r.at[idx_reg, "stato_comodato"] = "Reso/Concluso"
                                    carica_su_sheet(df_reg_r, "Registro_Comodati")
                                    df_inv_r = scarica_da_sheet("Inventario_Comodati")
                                    df_inv_r.loc[df_inv_r["id_bene"] == comodato['id_bene'], "stato"] = "Disponibile"
                                    carica_su_sheet(df_inv_r, "Inventario_Comodati")
                                    st.success("Reso salvato!"); st.rerun()

            with tab_tutti_comodati: st.dataframe(scarica_da_sheet("Inventario_Comodati"), use_container_width=True, hide_index=True)

        elif sezione_selezionata == "📊 Gestione Preventivi e Fornitori":
            if MODULO_PREVENTIVI_DISPONIBILE:
                mostra_interfaccia_preventivi(scarica_da_sheet, carica_su_sheet, invia_email_sistema, URL_INTERMEDIARIO_SILENZIOSO, df_istanze)
            else:
                st.info("ℹ️ Il modulo preventivi è configurato, ma il file `gestione_preventivi.py` non è ancora stato creato o caricato nella cartella.")

    # ==========================================
    # WORKFLOW INTERNO: OPERATORI MAGAZZINI STANDARD (ATA / OFFICINA)
    # ==========================================
    elif st.session_state.ruolo_utente == "magazziniere":
        st.markdown(f"## 📦 Magazzino Fisico: {st.session_state.magazzino_selezionato}")
        tab1, tab2 = st.tabs(["📋 Tabella Inventario Scorte", "➕ Segnala Fabbisogno Mancante (Acquisti)"])
        
        with tab1:
            st.dataframe(scarica_da_sheet(MAPPA_SCHEDE[st.session_state.magazzino_selezionato]["inventario"]), use_container_width=True, hide_index=True)
            
        with tab2:
            st.markdown("### Segnala rotture di stock o materiale da acquistare")
            st.markdown("L'istanza finirà nella sezione dell'Ufficio Tecnico per richiedere i preventivi alle ditte.")
            with st.form("form_fabb_standard"):
                mat = st.text_input("Descrizione materiale richiesto:")
                qta = st.text_input("Quantità o pacchi stimati:")
                note = st.text_area("Note urgenza:")
                if st.form_submit_button("Invia Segnalazione Fabbisogno"):
                    if mat.strip():
                        df_rm = scarica_da_sheet("Richieste_Preventivo_Magazzino")
                        id_rm = 2001 if df_rm.empty else int(pd.to_numeric(df_rm["id_richiesta_mag"], errors='coerce').max()) + 1
                        nuovo = pd.DataFrame([{"id_richiesta_mag": id_rm, "data_creazione": datetime.now().strftime("%d/%m/%Y %H:%M"), "magazzino_origine": st.session_state.magazzino_selezionato, "materiale_richiesto": mat, "quantita_esimata": qta, "stato_iter": "In attesa di preventivi", "note": note}])
                        carica_su_sheet(pd.concat([df_rm, nuovo], ignore_index=True), "Richieste_Preventivo_Magazzino")
                        st.success(f"Richiesta inoltrata! ID REQ interna: {id_rm}")
                    else: st.error("Specificare il materiale.")
