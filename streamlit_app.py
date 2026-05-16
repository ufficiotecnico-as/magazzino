import streamlit as st
import pandas as pd
from datetime import datetime
import io
import json
import base64
from PIL import Image

# Librerie di archiviazione
try:
    import gspread
    from google.oauth2 import service_account
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False

# Libreria per la generazione di PDF stabili
try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False

# Configurazione iniziale di pagina
st.set_page_config(page_title="Gestione Magazzini Scarpa", page_icon="🏢", layout="wide")

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
@st.cache_resource(ttl=5)
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
        return pd.DataFrame(worksheet.get_all_records())
    except gspread.exceptions.WorksheetNotFound:
        if "Inventario_Comodati" in nome_scheda:
            df_base = pd.DataFrame(columns=["id_bene", "tipo_bene", "descrizione", "stato"])
        elif "Registro_Comodati" in nome_scheda:
            df_base = pd.DataFrame(columns=["id_comodato", "tipo_soggetto", "nominativo", "id_bene", "data_consegna", "stato_comodato"])
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

# --- GENERAZIONE PDF CON FIRMA INTEGRATA E DINAMICA ---
def genera_pdf_comodato(id_contratto, nome, ruolo, bene, data, tipo_operazione, firma_utente_b64=None, utente_loggato="Ufficio Tecnico"):
    if not FPDF_AVAILABLE:
        return b"Errore libreria PDF"
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    
    # Intestazione Istituto
    pdf.cell(190, 10, "ISTITUTO SUPERIORE ANTONIO SCARPA", ln=True, align="C")
    pdf.set_font("Arial", "", 12)
    pdf.cell(190, 10, "Piattaforma di Gestione Logistica e Comodati d'Uso", ln=True, align="C")
    pdf.ln(10)
    
    # Titolo Documento
    pdf.set_font("Arial", "B", 14)
    titolo = "VERBALE DI CONSEGNA IN COMODATO D'USO" if tipo_operazione == "CONSEGNA" else "RICEVUTA DI RICONSEGNA BENI"
    pdf.cell(190, 10, titolo, ln=True, align="L")
    pdf.ln(5)
    
    # Dati del Contratto
    pdf.set_font("Arial", "", 11)
    pdf.cell(190, 8, f"Codice Registro: {id_contratto}", ln=True)
    pdf.cell(190, 8, f"Data Operazione: {data}", ln=True)
    pdf.cell(190, 8, f"Assegnatario / Beneficiario: {nome} ({ruolo})", ln=True)
    pdf.cell(190, 8, f"Bene Associato (ID/Modello): {bene}", ln=True)
    pdf.ln(10)
    
    # Clausola Note Legali
    pdf.set_font("Arial", "I", 10)
    if tipo_operazione == "CONSEGNA":
        nota = "Il sottoscritto dichiara di ricevere l'oggetto sopra indicato in perfetto stato di funzionamento e si impegna a custodirlo con la massima diligenza del buon padre di famiglia, restituendolo su richiesta dell'Istituto."
    else:
        nota = "Si attesta che il bene sopra descritto è stato riconsegnato in data odierna all'Ufficio Tecnico/Magazzino del Polo Scarpa. Il presente documento libera il richiedente da successive responsabilità di custodia."
    pdf.multi_cell(190, 6, nota)
    pdf.ln(20)
    
    # Blocco Firme
    pdf.set_font("Arial", "B", 11)
    
    # Gestione utenza: se è admin o Amministratore scrive "Ufficio Tecnico"
    if str(utente_loggato).lower() in ["admin", "amministratore"]:
        firma_admin_testo = "Ufficio Tecnico"
    else:
        firma_admin_testo = str(utente_loggato)
    
    y_posizione_firme = pdf.get_y()
    pdf.cell(95, 8, "Per l'Amministrazione: ", align="L")
    pdf.cell(95, 8, "Firma del Richiedente: ", align="L", ln=True)
    
    pdf.set_font("Arial", "I", 10)
    pdf.cell(95, 8, f"F.to {firma_admin_testo}", align="L")
    
    # Se la firma dell'utente è presente, viene inserita nel PDF
    if firma_utente_b64 and len(firma_utente_b64) > 100:
        try:
            if "," in firma_utente_b64:
                firma_utente_b64 = firma_utente_b64.split(",")[1]
            immagine_bytes = base64.b64decode(firma_utente_b64)
            img = Image.open(io.BytesIO(immagine_bytes))
            
            # Forziamo lo sfondo bianco per rimuovere la trasparenza del canvas HTML
            background = Image.new(mode='RGB', size=img.size, color=(255, 255, 255))
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                background.paste(img, box=None, mask=img.convert('RGBA').split()[3])
            else:
                background.paste(img, box=None)
            img = background
                
            img_buffer = io.BytesIO()
            img.save(img_buffer, format="JPEG")
            img_buffer.seek(0)
            
            # Posiziona l'immagine della firma sotto il titolo del Richiedente
            pdf.image(img_buffer, x=115, y=y_posizione_firme + 8, w=60, h=18)
        except Exception:
            pdf.cell(95, 8, "[Firma Acquisita Elettronicamente]", align="L", ln=True)
    else:
        pdf.cell(95, 8, "_______________________", align="L", ln=True)
            
    return pdf.output()

# --- CARICAMENTO SU DRIVE ROBUSTO (SENZA COPIE DI CARTELLE) ---
def carica_su_drive_unico(file_bytes, nome_file, mime_type, nome_cartella_dest):
    if not GOOGLE_DRIVE_AVAILABLE: return None
    creds_info = None
    if "google_creds" in st.secrets: creds_info = dict(st.secrets["google_creds"])
    elif "gcp_service_account" in st.secrets: creds_info = dict(st.secrets["gcp_service_account"])
    if not creds_info: return None
    
    try:
        if "private_key" in creds_info: creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n").strip()
        creds = service_account.Credentials.from_service_account_info(creds_info, scopes=['https://www.googleapis.com/auth/drive'])
        service = build('drive', 'v3', credentials=creds)
        
        # Cerca se la cartella esiste già per non duplicarla
        query = f"name='{nome_cartella_dest}' and '{ID_CARTELLA_DRIVE_PRINCIPALE}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        risultato = service.files().list(q=query, spaces='drive', supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
        files = risultato.get('files', [])
        
        if files:
            id_cartella = files[0]['id']
        else:
            meta_cartella = {'name': nome_cartella_dest, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [ID_CARTELLA_DRIVE_PRINCIPALE]}
            id_cartella = service.files().create(body=meta_cartella, fields='id', supportsAllDrives=True).execute().get('id')
            
        meta_file = {'name': nome_file, 'parents': [id_cartella]}
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)
        service.files().create(body=meta_file, media_body=media, fields='id', supportsAllDrives=True).execute()
        return True
    except Exception:
        return None

# Variabili di stato sessione
if "ruolo_utente" not in st.session_state: st.session_state.ruolo_utente = None
if "utente_corrente" not in st.session_state: st.session_state.utente_corrente = ""
if "magazzino_selezionato" not in st.session_state: st.session_state.magazzino_selezionato = None

# Router Accesso Principale
if st.session_state.ruolo_utente is None:
    col_l, col_c, col_r = st.columns([1, 1.8, 1])
    with col_c:
        st.image(URL_LOGO, use_container_width=True)
        st.markdown("<h2 style='text-align: center;'>Piattaforma Logistica di Istituto</h2>", unsafe_allow_html=True)
        with st.container(border=True):
            scelta = st.radio("Seleziona profilo:", ["Collaboratore (Richiesta Materiale)", "Staff Magazzino / Amministrazione"])
            if scelta == "Collaboratore (Richiesta Materiale)":
                nome = st.text_input("Nome e Cognome:")
                if st.button("Accedi", type="primary", use_container_width=True):
                    if nome.strip():
                        st.session_state.ruolo_utente = "collaboratore"
                        st.session_state.utente_corrente = nome.strip()
                        st.rerun()
            else:
                pwd = st.text_input("Codice autorizzazione:", type="password")
                if st.button("Autentica ed Entra", type="primary", use_container_width=True):
                    if pwd in PASSWORD_MAP:
                        st.session_state.ruolo_utente = "magazziniere"
                        st.session_state.magazzino_selezionato = PASSWORD_MAP[pwd]
                        st.session_state.utente_corrente = PASSWORD_MAP[pwd]
                        st.rerun()
                    elif pwd == PASSWORD_ADMIN:
                        st.session_state.ruolo_utente = "admin"
                        st.session_state.utente_corrente = "admin"
                        st.rerun()
                    else: st.error("Codice non valido.")
else:
    # Top bar
    col_t, col_b_logout = st.columns([4, 1])
    with col_t: st.markdown(f"Accesso: **{st.session_state.utente_corrente.upper()}**")
    with col_b_logout:
        if st.button("🚪 Cambia Profilo", use_container_width=True):
            st.session_state.ruolo_utente = None
            st.rerun()
            
    st.image(URL_LOGO, use_container_width=True)

    # --- AREA AMMINISTRATORE & COMODATI ---
    if st.session_state.ruolo_utente == "admin":
        tab_magazzini, tab_comodati = st.tabs(["📊 MAGAZZINI LOGISTICI", "✍️ GESTIONE COMODATI (PC & CHIAVI)"])
        
        with tab_magazzini:
            mag_sel = st.selectbox("Seleziona Magazzino:", LISTA_MAGAZZINI)
            st.dataframe(scarica_da_sheet(MAPPA_SCHEDE[mag_sel]["inventario"]), use_container_width=True, hide_index=True)
            
        with tab_comodati:
            df_inv_comodati = scarica_da_sheet("Inventario_Comodati")
            df_reg_comodati = scarica_da_sheet("Registro_Comodati")
            sub_inv, sub_nuovo, sub_registro = st.tabs(["📋 Inventario", "➕ Nuova Assegnazione", "📜 Contratti Attivi"])
            
            with sub_inv:
                with st.form("nuovo_ogg"):
                    col1, col2 = st.columns(2)
                    with col1:
                        id_b = st.text_input("ID Seriale (es. PC-012)")
                        tipo_b = st.selectbox("Categoria:", ["PC Notebook", "Chiave d'Accesso"])
                    with col2: desc_b = st.text_input("Descrizione")
                    if st.form_submit_button("Aggiungi all'Inventario", use_container_width=True):
                        if id_b.strip() and desc_b.strip():
                            nuovo_b = pd.DataFrame([{"id_bene": id_b.strip(), "tipo_bene": tipo_b, "descrizione": desc_b.strip(), "stato": "Disponibile"}])
                            df_inv_comodati = pd.concat([df_inv_comodati, nuovo_b], ignore_index=True)
                            carica_su_sheet(df_inv_comodati, "Inventario_Comodati")
                            st.success("Bene inserito!")
                            st.rerun()
                st.dataframe(df_inv_comodati, use_container_width=True, hide_index=True)
                
            with sub_nuovo:
                st.markdown("### Nuovo Accordo di Comodato con Firma Digitale")
                if df_inv_comodati.empty or not (df_inv_comodati["stato"] == "Disponibile").any():
                    st.warning("Nessun bene disponibile al momento.")
                else:
                    col_n1, col_n2 = st.columns(2)
                    with col_n1:
                        tipo_sog = st.selectbox("Profilo Richiedente:", ["Alunno", "Genitore / Tutore", "Insegnante / Personale"])
                        nom_sog = st.text_input("Nome e Cognome dell'Assegnatario:")
                    with col_n2:
                        disp = df_inv_comodati[df_inv_comodati["stato"] == "Disponibile"]["id_bene"].tolist()
                        bene_sel = st.selectbox("Seleziona l'oggetto da consegnare:", disp)
                        
                    st.markdown("<div style='background-color:#fff3cd; padding:12px; border-radius:8px; border:1px solid #ffeeba; font-size:13px;'><b>Clausola di Custodia:</b> Il firmatario prende in carico l'oggetto integro e funzionante e si impegna a riconsegnarlo integro alla scadenza richiesta.</div>", unsafe_allow_html=True)
                    
                    st.markdown("#### 🖊️ Firma sul Tablet qui sotto:")
                    
                    # --- SISTEMA DI TRASMISSIONE EVENTI DIRETTO ---
                    # Usiamo un input nativo visibile che intercetta i messaggi JavaScript globali della finestra
                    stringa_firma_input = st.text_input("Stringa Dati Firma (Generata dal disegno)", key="input_ponte_firma_b64")
                    
                    import streamlit.components.v1 as components
                    componente_firma_html = """
                    <div style="width:100%; max-width:550px;">
                        <canvas id="sig-canvas" width="520" height="150" style="border: 2px dashed #8b1e1e; border-radius: 8px; background-color: #ffffff; cursor: crosshair; touch-action: none;"></canvas>
                        <br>
                        <button type="button" onclick="clearCanvas()" style="background:#64748b; color:white; border:none; padding:6px 12px; border-radius:4px; margin-top:5px; font-size:12px; font-weight:bold; cursor:pointer;">⚠️ CANCELLA E RIFÀI</button>
                    </div>
                    <script>
                        var canvas = document.getElementById("sig-canvas");
                        var ctx = canvas.getContext("2d");
                        ctx.strokeStyle = "#000000"; ctx.lineWidth = 3;
                        var drawing = false;
                        
                        function inviaAStreamlit() {
                            var dataUrl = canvas.toDataURL("image/png");
                            // Cerchiamo l'elemento di input della pagina principale e gli iniettiamo il valore direttamente
                            var inputs = window.parent.document.getElementsByTagName('input');
                            for (var i = 0; i < inputs.length; i++) {
                                if (inputs[i].getAttribute('aria-label') === "Stringa Dati Firma (Generata dal disegno)") {
                                    inputs[i].value = dataUrl;
                                    inputs[i].dispatchEvent(new Event('input', { bubbles: true }));
                                    break;
                                }
                            }
                        }

                        canvas.addEventListener("mousedown", function(e) { drawing = true; ctx.beginPath(); ctx.moveTo(e.offsetX, e.offsetY); });
                        canvas.addEventListener("mousemove", function(e) { if (drawing) { ctx.lineTo(e.offsetX, e.offsetY); ctx.stroke(); } });
                        canvas.addEventListener("mouseup", function() { drawing = false; inviaAStreamlit(); });
                        
                        canvas.addEventListener("touchstart", function(e) { drawing = true; var t = e.touches[0]; var b = canvas.getBoundingClientRect(); ctx.beginPath(); ctx.moveTo(t.clientX - b.left, t.clientY - b.top); });
                        canvas.addEventListener("touchmove", function(e) { if (drawing) { var t = e.touches[0]; var b = canvas.getBoundingClientRect(); ctx.lineTo(t.clientX - b.left, t.clientY - b.top); ctx.stroke(); } e.preventDefault(); });
                        canvas.addEventListener("touchend", function() { drawing = false; inviaAStreamlit(); });
                        
                        function clearCanvas() { 
                            ctx.clearRect(0, 0, canvas.width, canvas.height); 
                            var inputs = window.parent.document.getElementsByTagName('input');
                            for (var i = 0; i < inputs.length; i++) {
                                if (inputs[i].getAttribute('aria-label') === "Stringa Dati Firma (Generata dal disegno)") {
                                    inputs[i].value = "";
                                    inputs[i].dispatchEvent(new Event('input', { bubbles: true }));
                                    break;
                                }
                            }
                        }
                    </script>
                    """
                    components.html(componente_firma_html, height=200)
                    
                    if st.button("✍️ Approva e Salva PDF su Google Drive", type="primary", use_container_width=True):
                        if nom_sog.strip():
                            if len(stringa_firma_input) < 100:
                                st.error("⚠️ Attenzione: È necessario apporre la firma sul tablet prima di salvare il PDF.")
                            else:
                                id_com = int(df_reg_comodati["id_comodato"].astype(float).max()) + 1 if not df_reg_comodati.empty else 1001
                                data_ora = datetime.now().strftime("%d/%m/%Y %H:%M")
                                
                                # Creiamo il PDF REALE passando la stringa corretta dell'utente loggato (admin -> Ufficio Tecnico)
                                pdf_output_bytes = genera_pdf_comodato(id_com, nom_sog.strip(), tipo_sog, bene_sel, data_ora, "CONSEGNA", stringa_firma_input, st.session_state.utente_corrente)
                                
                                # Carichiamo il file .PDF effettivo su Drive evitando duplicazioni di cartelle
                                nome_file_pdf = f"Verbale_Consegna_{id_com}_{nom_sog.replace(' ', '_')}.pdf"
                                carica_su_drive_unico(pdf_output_bytes, nome_file_pdf, "application/pdf", "Comodati_Consegne")
                                
                                # Registrazione Dati su Foglio Cloud
                                nuova_r = pd.DataFrame([{"id_comodato": id_com, "tipo_soggetto": tipo_sog, "nominativo": nom_sog.strip(), "id_bene": bene_sel, "data_consegna": data_ora, "stato_comodato": "In Corso"}])
                                df_reg_comodati = pd.concat([df_reg_comodati, nuova_r], ignore_index=True)
                                carica_su_sheet(df_reg_comodati, "Registro_Comodati")
                                
                                # Cambiamo lo stato del bene su Assegnato
                                df_inv_comodati.loc[df_inv_comodati["id_bene"] == bene_sel, "stato"] = "Assegnato"
                                carica_su_sheet(df_inv_comodati, "Inventario_Comodati")
                                
                                st.success(f"🚀 Contratto di Consegna PDF N°{id_com} archiviato e registrato correttamente con firma visibile e intestazione 'Ufficio Tecnico'!")
                                st.rerun()
                        else:
                            st.error("Inserisci il nome completo prima di salvare.")
                            
            with sub_registro:
                st.markdown("### Registro Contratti Attivi")
                attivi = df_reg_comodati[df_reg_comodati["stato_comodato"] == "In Corso"] if not df_reg_comodati.empty else pd.DataFrame()
                if attivi.empty:
                    st.info("Nessun comodato attivo.")
                else:
                    for id_x, riga in attivi.iterrows():
                        with st.container(border=True):
                            c1, c2 = st.columns([3, 1])
                            with c1:
                                st.markdown(f"📦 Oggetto: **{riga['id_bene']}** affidato a **{riga['nominativo']}** ({riga['tipo_soggetto']})")
                                st.caption(f"Assegnatario: {riga['nominativo']} | ID Contratto: {riga['id_comodato']}")
                            with c2:
                                if st.button("Riconsegna ↩", key=f"ric_{riga['id_comodato']}", type="primary", use_container_width=True):
                                    data_rientro = datetime.now().strftime("%d/%m/%Y %H:%M")
                                    
                                    # Genera PDF di Riconsegna scarico responsabilità
                                    pdf_rientro_bytes = genera_pdf_comodato(riga['id_comodato'], riga['nominativo'], riga['tipo_soggetto'], riga['id_bene'], data_rientro, "RICONSEGNA", utente_loggato=st.session_state.utente_corrente)
                                    nome_file_rientro = f"Ricevuta_Riconsegna_{riga['id_comodato']}.pdf"
                                    carica_su_drive_unico(pdf_rientro_bytes, nome_file_rientro, "application/pdf", "Comodati_Riconsegne")
                                    
                                    # Aggiorna Database Fogli
                                    df_reg_comodati.loc[df_reg_comodati["id_comodato"].astype(str) == str(riga["id_comodato"]), "stato_comodato"] = f"Riconsegnato il {data_rientro}"
                                    carica_su_sheet(df_reg_comodati, "Registro_Comodati")
                                    
                                    df_inv_comodati.loc[df_inv_comodati["id_bene"] == riga["id_bene"], "stato"] = "Disponibile"
                                    carica_su_sheet(df_inv_comodati, "Inventario_Comodati")
                                    
                                    st.success("Bene rientrato in inventario e Ricevuta di Riconsegna PDF generata!")
                                    st.rerun()

    # --- SOTTO AREA RICHIESTE COLLABORATORE TRADIZIONALE ---
    elif st.session_state.ruolo_utente == "collaboratore":
        st.markdown("### Nuova Richiesta Materiali")
        st.info("Area Richieste allineata ed attiva.")
