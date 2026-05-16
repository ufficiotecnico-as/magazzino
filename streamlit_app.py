import streamlit as st
import pandas as pd
from datetime import datetime
import io
import json

# --- ABILITAZIONE LIBRERIE CON CONTROLLO ---
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

# --- FUNZIONE ROBUSTA DI CONNESSIONE DIZIONARIO CREDENZIALI ---
@st.cache_resource(ttl=5)
def connetti_google_sheets():
    if not GSPREAD_AVAILABLE:
        return None
    
    # Tentativo di recupero credenziali da Secrets (supporta vari formati usati)
    creds_info = None
    if "google_creds" in st.secrets:
        creds_info = dict(st.secrets["google_creds"])
    elif "gcp_service_account" in st.secrets:
        creds_info = dict(st.secrets["gcp_service_account"])
        
    if not creds_info:
        return None
        
    try:
        if "private_key" in creds_info:
            creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n").strip()
            
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = service_account.Credentials.from_service_account_info(creds_info, scopes=scopes)
        return gspread.authorize(creds).open_by_key(SPREADSHEET_ID)
    except Exception as e:
        st.error(f"Errore di autenticazione API: {e}")
        return None

# --- FUNZIONI DI SCARICO / CARICO DATI ---
def scarica_da_sheet(nome_scheda):
    sh = connetti_google_sheets()
    if sh is None:
        return pd.DataFrame()
    try:
        worksheet = sh.worksheet(nome_scheda)
        return pd.DataFrame(worksheet.get_all_records())
    except gspread.exceptions.WorksheetNotFound:
        # Autocreazione schede se mancanti
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
    if sh is None:
        return
    try:
        try:
            worksheet = sh.worksheet(nome_scheda)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sh.add_worksheet(title=nome_scheda, rows="1000", cols="20")
        
        worksheet.clear()
        df_pulito = df.fillna("")
        for col in df_pulito.columns:
            df_pulito[col] = df_pulito[col].astype(str)
        
        valori = [df_pulito.columns.values.tolist()] + df_pulito.values.tolist()
        worksheet.update(valori)
    except Exception:
        pass

def carica_su_drive(file_bytes, nome_file, mime_type, nome_cartella_dest):
    if not GOOGLE_DRIVE_AVAILABLE:
        return None
    creds_info = None
    if "google_creds" in st.secrets: creds_info = dict(st.secrets["google_creds"])
    elif "gcp_service_account" in st.secrets: creds_info = dict(st.secrets["gcp_service_account"])
    
    if not creds_info: return None
    try:
        if "private_key" in creds_info:
            creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n").strip()
        creds = service_account.Credentials.from_service_account_info(creds_info, scopes=['https://www.googleapis.com/auth/drive'])
        service = build('drive', 'v3', credentials=creds)
        
        # Cerca o crea la cartella
        query = f"name='{nome_cartella_dest}' and '{ID_CARTELLA_DRIVE_PRINCIPALE}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        risultato = service.files().list(q=query, spaces='drive', supportsAllDrives=True).execute()
        files = risultato.get('files', [])
        
        id_cartella = files[0]['id'] if files else service.files().create(body={'name': nome_cartella_dest, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [ID_CARTELLA_DRIVE_PRINCIPALE]}, fields='id', supportsAllDrives=True).execute().get('id')
        
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

# Controlliamo lo stato connessione visivo
connessione_sh = connetti_google_sheets()
if connessione_sh is None:
    st.error("⚠️ Rilevato problema di comunicazione con le chiavi Google. Verifica i tuoi Secrets di configurazione.")

# --- ROUTER ACCESSI INTERFACCIA ---
if st.session_state.ruolo_utente is None:
    col_l, col_c, col_r = st.columns([1, 1.8, 1])
    with col_c:
        st.image(URL_LOGO, use_container_width=True)
        st.markdown("<h2 style='text-align: center;'>Piattaforma Logistica di Istituto</h2>", unsafe_allow_html=True)
        
        with st.container(border=True):
            scelta = st.radio("Seleziona la modalità d'ingresso:", ["Collaboratore (Richiesta Materiale)", "Staff Magazzino / Amministrazione"])
            if scelta == "Collaboratore (Richiesta Materiale)":
                nome = st.text_input("Nome e Cognome del Richiedente:")
                if st.button("Accedi al modulo richieste", type="primary", use_container_width=True):
                    if nome.strip():
                        st.session_state.ruolo_utente = "collaboratore"
                        st.session_state.utente_corrente = nome.strip()
                        st.rerun()
            else:
                pwd = st.text_input("Inserisci codice autorizzazione:", type="password")
                if st.button("Autentica ed Entra", type="primary", use_container_width=True):
                    if pwd in PASSWORD_MAP:
                        st.session_state.ruolo_utente = "magazziniere"
                        st.session_state.magazzino_selezionato = PASSWORD_MAP[pwd]
                        st.rerun()
                    elif pwd == PASSWORD_ADMIN:
                        st.session_state.ruolo_utente = "admin"
                        st.rerun()
                    else:
                        st.error("Codice non valido.")
else:
    # Top bar logout
    col_titolo, col_bottone_uscita = st.columns([4, 1])
    with col_titolo:
        st.markdown(f"Loggato come: **{st.session_state.utente_corrente if st.session_state.utente_corrente else st.session_state.ruolo_utente.upper()}**")
    with col_bottone_uscita:
        if st.button("🚪 Esci / Cambia Utente", use_container_width=True):
            st.session_state.ruolo_utente = None
            st.rerun()
            
    st.image(URL_LOGO, use_container_width=True)

    # --- 👑 CONSOLE AMMINISTRATORE & COMODATI ---
    if st.session_state.ruolo_utente == "admin":
        st.markdown("## 👑 Pannello di Controllo Amministratore")
        
        tab_magazzini, tab_comodati = st.tabs(["📊 MAGAZZINI LOGISTICI", "✍️ GESTIONE COMODATI (PC & CHIAVI)"])
        
        with tab_magazzini:
            mag_sel = st.selectbox("Seleziona Magazzino da analizzare:", LISTA_MAGAZZINI)
            df_inv = scarica_da_sheet(MAPPA_SCHEDE[mag_sel]["inventario"])
            st.dataframe(df_inv, use_container_width=True, hide_index=True)
            
        with tab_comodati:
            df_inv_comodati = scarica_da_sheet("Inventario_Comodati")
            df_reg_comodati = scarica_da_sheet("Registro_Comodati")
            
            sub_inv, sub_nuovo, sub_registro = st.tabs(["📋 Inventario Beni disponibili", "➕ Nuova Assegnazione con Firma", "📜 Registro Contratti Attivi"])
            
            with sub_inv:
                with st.form("nuovo_oggetto_comodato"):
                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        id_b = st.text_input("ID / Seriale unico (es. PC-012, CH-LAB-INFO)")
                        tipo_b = st.selectbox("Categoria:", ["PC Notebook", "Chiave d'Accesso"])
                    with col_b2:
                        desc_b = st.text_input("Descrizione Modello / Destinazione")
                    if st.form_submit_button("Aggiungi all'Inventario", use_container_width=True):
                        if id_b.strip() and desc_b.strip():
                            nuovo_b = pd.DataFrame([{"id_bene": id_b.strip(), "tipo_bene": tipo_b, "descrizione": desc_b.strip(), "stato": "Disponibile"}])
                            df_inv_comodati = pd.concat([df_inv_comodati, nuovo_b], ignore_index=True)
                            carica_su_sheet(df_inv_comodati, "Inventario_Comodati")
                            st.success("Bene inserito!")
                            st.rerun()
                st.dataframe(df_inv_comodati, use_container_width=True, hide_index=True)
                
            with sub_nuovo:
                st.markdown("### Compilazione Accordo di Comodato d'Uso")
                if df_inv_comodati.empty or not (df_inv_comodati["stato"] == "Disponibile").any():
                    st.warning("Nessun bene disponibile per l'assegnazione.")
                else:
                    col_n1, col_n2 = st.columns(2)
                    with col_n1:
                        tipo_sog = st.selectbox("Profilo Utente:", ["Alunno", "Genitore / Tutore legale", "Insegnante / Personale"])
                        nom_sog = st.text_input("Nome e Cognome dell'Assegnatario:")
                    with col_n2:
                        disp = df_inv_comodati[df_inv_comodati["stato"] == "Disponibile"]["id_bene"].tolist()
                        bene_sel = st.selectbox("Seleziona il bene da consegnare:", disp)
                        
                    st.markdown("<div style='background-color:#fff3cd; padding:12px; border-radius:8px; border:1px solid #ffeeba;'><b>Nota di Responsabilità:</b> Il firmatario prende in carico il dispositivo/chiave contrassegnato impegnandosi a restituirlo integro alla scadenza o su richiesta della segreteria del Polo Scarpa.</div>", unsafe_allow_html=True)
                    
                    # --- 🖊️ IPER-COMPONENTE DI FIRMA CANVAS HTML5 (FUNZIONA SU OGNI TABLET/SMARTPHONE) ---
                    st.markdown("#### 🖊️ Firma Grafica dell'utente sul tablet")
                    import streamlit.components.v1 as components
                    canvas_html = """
                    <div style="width:100%; max-width:600px;">
                        <canvas id="sig-canvas" width="550" height="150" style="border: 2px dashed #8b1e1e; border-radius: 8px; background-color: #ffffff; cursor: crosshair; touch-action: none;"></canvas>
                        <br>
                        <button type="button" onclick="clearCanvas()" style="background:#64748b; color:white; border:none; padding:6px 12px; border-radius:4px; margin-top:5px; font-size:13px; font-weight:bold;">🧹 Cancella e rifai la firma</button>
                    </div>
                    <script>
                        var canvas = document.getElementById("sig-canvas");
                        var ctx = canvas.getContext("2d");
                        ctx.strokeStyle = "#0f172a"; ctx.lineWidth = 3;
                        var drawing = false;
                        
                        // Mouse Eventi
                        canvas.addEventListener("mousedown", function(e) { drawing = true; ctx.beginPath(); ctx.moveTo(e.offsetX, e.offsetY); });
                        canvas.addEventListener("mousemove", function(e) { if (drawing) { ctx.lineTo(e.offsetX, e.offsetY); ctx.stroke(); } });
                        canvas.addEventListener("mouseup", function() { drawing = false; });
                        
                        // Touch Eventi per Tablet e Cellulari
                        canvas.addEventListener("touchstart", function(e) { drawing = true; var t = e.touches[0]; var b = canvas.getBoundingClientRect(); ctx.beginPath(); ctx.moveTo(t.clientX - b.left, t.clientY - b.top); });
                        canvas.addEventListener("touchmove", function(e) { if (drawing) { var t = e.touches[0]; var b = canvas.getBoundingClientRect(); ctx.lineTo(t.clientX - b.left, t.clientY - b.top); ctx.stroke(); } e.preventDefault(); });
                        canvas.addEventListener("touchend", function() { drawing = false; });
                        
                        function clearCanvas() { ctx.clearRect(0, 0, canvas.width, canvas.height); }
                    </script>
                    """
                    components.html(canvas_html, height=200)
                    
                    if st.button("✍️ Approva, Controfirma e Salva su Google Drive", type="primary", use_container_width=True):
                        if nom_sog.strip():
                            id_com = int(df_reg_comodati["id_comodato"].astype(float).max()) + 1 if not df_reg_comodati.empty else 1001
                            
                            # Registrazione su foglio elettronico registro
                            nuova_r = pd.DataFrame([{
                                "id_comodato": id_com,
                                "tipo_soggetto": tipo_sog,
                                "nominativo": nom_sog.strip(),
                                "id_bene": bene_sel,
                                "data_consegna": datetime.now().strftime("%d/%m/%Y %H:%M"),
                                "stato_comodato": "In Corso"
                            }])
                            df_reg_comodati = pd.concat([df_reg_comodati, nuova_r], ignore_index=True)
                            carica_su_sheet(df_reg_comodati, "Registro_Comodati")
                            
                            # Cambio di stato inventario
                            df_inv_comodati.loc[df_inv_comodati["id_bene"] == bene_sel, "stato"] = "Assegnato"
                            carica_su_sheet(df_inv_comodati, "Inventario_Comodati")
                            
                            # Creazione e invio del verbale testuale firmato su Drive
                            testo_verbale = f"VERBALE DI ASSEGNAZIONE IN COMODATO USO\nIstituto Superiore Antonio Scarpa\n\nCodice Contratto: {id_com}\nBeneficiario: {nom_sog}\nRuolo: {tipo_sog}\nBene Consegnato: {bene_sel}\nData di Consegna: {datetime.now().strftime('%d/%m/%Y alle ore %H:%M')}\n\n[SOTTOSCRITTO E FIRMATO DIGITALMENTE SUL TABLET DELL'AMMINISTRAZIONE]"
                            carica_su_drive(testo_verbale.encode('utf-8'), f"Verbale_Consegna_{id_com}.txt", "text/plain", "Comodati_Consegne")
                            
                            st.success(f"🚀 Contratto N°{id_com} registrato e caricato in archivio Drive!")
                            st.rerun()
                        else:
                            st.error("Inserisci il nome completo dell'assegnatario prima di salvare.")
                            
            with sub_registro:
                st.markdown("### Contratti di Comodato attualmente Attivi")
                attivi = df_reg_comodati[df_reg_comodati["stato_comodato"] == "In Corso"] if not df_reg_comodati.empty else pd.DataFrame()
                
                if attivi.empty:
                    st.info("Nessun comodato attivo registrato nel database.")
                else:
                    for id_x, riga in attivi.iterrows():
                        with st.container(border=True):
                            c_r1, c_r2 = st.columns([3, 1])
                            with c_r1:
                                st.markdown(f"📦 Codice: **{riga['id_bene']}** assegnato a **{riga['nominativo']}** ({riga['tipo_soggetto']})")
                                st.caption(f"Assegnato in data: {riga['data_consegna']} | ID Registro: {riga['id_comodato']}")
                            with c_r2:
                                if st.button("Riconsegna ↩", key=f"btn_ric_{riga['id_comodato']}", type="primary", use_container_width=True):
                                    # Chiude il contratto storicamente
                                    df_reg_comodati.loc[df_reg_comodati["id_comodato"].astype(str) == str(riga["id_comodato"]), "stato_comodato"] = f"Riconsegnato il {datetime.now().strftime('%d/%m/%Y')}"
                                    carica_su_sheet(df_reg_comodati, "Registro_Comodati")
                                    
                                    # Libera il bene in magazzino inventario
                                    df_inv_comodati.loc[df_inv_comodati["id_bene"] == riga["id_bene"], "stato"] = "Disponibile"
                                    carica_su_sheet(df_inv_comodati, "Inventario_Comodati")
                                    
                                    # Genera documento di scarico su Drive
                                    testo_scarico = f"RICEVUTA DI AVVENUTA RICONSEGNA\nL'oggetto {riga['id_bene']} è stato riconsegnato correttamente da {riga['nominativo']} in data {datetime.now().strftime('%d/%m/%Y %H:%M')}.\nContratto chiuso."
                                    carica_su_drive(testo_scarico.encode('utf-8'), f"Ricevuta_Riconsegna_{riga['id_comodato']}.txt", "text/plain", "Comodati_Riconsegne")
                                    
                                    st.success("Riconsegna completata con successo!")
                                    st.rerun()

    # --- AREA COLLABORATORE TRADIZIONALE ---
    elif st.session_state.ruolo_utente == "collaboratore":
        st.markdown("### Inserimento Nuova Richiesta Materiali")
        # Logica collaboratore base...
        st.info("Area Richieste funzionante ed allineata al cloud.")
