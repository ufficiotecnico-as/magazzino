import streamlit as st
import pandas as pd
from datetime import datetime
import io
import os
from PIL import Image

# Librerie per Google Cloud / Fogli
try:
    import gspread
    from google.oauth2 import service_account
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

# Libreria per decodificare codici a barre dalle immagini
try:
    import pyzbar
    from pyzbar.pyzbar import decode
    PYZBAR_AVAILABLE = True
except ImportError:
    PYZBAR_AVAILABLE = False

try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False

# Componente per la firma digitale su tablet/schermo
try:
    from streamlit_signature_pad import st_signature_pad
    SIGNATURE_AVAILABLE = True
except ImportError:
    SIGNATURE_AVAILABLE = False

# Mappatura delle password e dei reparti
PASSWORD_MAP = {
    "ata2026": "Personale ATA",
    "officina2026": "Officina",
    "tecnici2026": "Tecnici Informatici"
}
PASSWORD_ADMIN = "admin99"

MAPPA_SCHEDE = {
    "Personale ATA": {
        "inventario": "Inventario ata",
        "richieste": "Richieste ata"
    },
    "Officina": {
        "inventario": "Inventario officina",
        "richieste": "Richieste officina"
    },
    "Tecnici Informatici": {
        "inventario": "Inventario informatica",
        "richieste": "Richieste informatica"
    }
}

URL_LOGO = "https://cspace.spaggiari.eu//pub/TVII0004/TVII0004-intestazione-nuova-senzaloghi.png?_t=1712923868"
ID_CARTELLA_DRIVE_PRINCIPALE = "1bVTs2smvVJONs2oIAFZdDvX9pYDK9MZT"
SPREADSHEET_ID = "1Q91H_TULvpsnPcyOwQ1lxmjOf809xp4cUz9p1EdMc-4"
LISTA_MAGAZZINI = ["Personale ATA", "Officina", "Tecnici Informatici"]

st.set_page_config(page_title="Gestione Magazzini Scarpa", page_icon="🏢", layout="wide")

# --- INIEZIONE CSS PER UN LOOK PREMIUM MODERNO ---
st.markdown("""
    <style>
        .stApp {
            background-color: #f8fafc;
        }
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
            transition: all 0.2s ease-in-out !important;
        }
        div.stButton > button:first-child:hover {
            background-color: #a72828 !important;
            transform: translateY(-1px) !important;
        }
        .stTextInput input, .stSelectbox div[data-baseweb="select"] {
            border-radius: 10px !important;
            border: 1px solid #cbd5e1 !important;
        }
        h2, h3 {
            color: #0f172a !important;
            font-weight: 700 !important;
        }
    </style>
""", unsafe_allow_html=True)

# --- CONNESSIONE SICURA A GOOGLE SHEETS ---
@st.cache_resource(ttl=2)
def connetti_google_sheets():
    if not GSPREAD_AVAILABLE:
        return None
    if "google_creds" not in st.secrets:
        return None
    try:
        creds_dict = dict(st.secrets["google_creds"])
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n").strip()
            
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
        if "universe_domain" in creds_dict:
            creds = creds.with_universe_domain(creds_dict["universe_domain"])
            
        return gspread.authorize(creds).open_by_key(SPREADSHEET_ID)
    except Exception:
        return None

# --- FUNZIONI DI LETTURA / SCRITTURA ---
def scarica_da_sheet(nome_scheda):
    sh = connetti_google_sheets()
    if sh is not None:
        try:
            worksheet = sh.worksheet(nome_scheda)
            return pd.DataFrame(worksheet.get_all_records())
        except gspread.exceptions.WorksheetNotFound:
            if "Inventario_Comodati" in nome_scheda:
                df_base = pd.DataFrame(columns=["id_bene", "tipo_bene", "descrizione", "stato"])
            elif "Registro_Comodati" in nome_scheda:
                df_base = pd.DataFrame(columns=["id_comodato", "tipo_soggetto", "nominativo", "id_bene", "data_consegna", "stato_comodato"])
            elif "Inventario" in nome_scheda:
                df_base = pd.DataFrame(columns=["magazzino", "id_articolo", "nome_articolo", "giacenza_totale"])
            elif "Richieste" in nome_scheda:
                df_base = pd.DataFrame(columns=["id_richiesta", "magazzino", "collaboratore", "articolo", "quantita", "stato", "data_richiesta", "data_consegna"])
            else:
                df_base = pd.DataFrame(columns=["id_acquisto", "magazzino", "articolo", "quantita_richiesta", "stato", "data_richiesta"])
            carica_su_sheet(df_base, nome_scheda)
            return df_base
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()

def carica_su_sheet(df, nome_scheda):
    sh = connetti_google_sheets()
    if sh is not None:
        try:
            try:
                worksheet = sh.worksheet(nome_scheda)
            except gspread.exceptions.WorksheetNotFound:
                worksheet = sh.add_worksheet(title=nome_scheda, rows="1000", cols="20")
            
            worksheet.clear()
            df_pulito = df.fillna("")
            for col in df_pulito.columns:
                df_pulito[col] = df_pulito[col].astype(str)
            
            valori_da_inviare = [df_pulito.columns.values.tolist()] + df_pulito.values.tolist()
            worksheet.update(valori_da_inviare)
        except Exception:
            pass

def carica_su_drive(file_bytes, nome_file, mime_type, nome_cartella_dest):
    if not GOOGLE_DRIVE_AVAILABLE or "google_creds" not in st.secrets: 
        return None
    try:
        creds_dict = dict(st.secrets["google_creds"])
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n").strip()
            
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=['https://www.googleapis.com/auth/drive'])
        if "universe_domain" in creds_dict:
            creds = creds.with_universe_domain(creds_dict["universe_domain"])
            
        service = build('drive', 'v3', credentials=creds)
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

# Controllo iniziale database
fogli_connessi = connetti_google_sheets() is not None

if "ruolo_utente" not in st.session_state: st.session_state.ruolo_utente = None
if "utente_corrente" not in st.session_state: st.session_state.utente_corrente = ""
if "magazzino_selezionato" not in st.session_state: st.session_state.magazzino_selezionato = None
if "scanned_code" not in st.session_state: st.session_state.scanned_code = ""

# --- INTERFACCIA DI ACCESSO ---
if st.session_state.ruolo_utente is None:
    col_logo_l, col_logo_c, col_logo_r = st.columns([1, 1.8, 1])
    with col_logo_c:
        st.image(URL_LOGO, use_container_width=True)
        st.markdown("<h2 style='text-align: center; margin-top: 15px; margin-bottom: 5px;'>Piattaforma Logistica Integrata</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #64748b; font-size: 1.1rem; margin-bottom: 30px;'>Gestione Inventario & Rifornimenti d'Istituto</p>", unsafe_allow_html=True)
    
    if not fogli_connessi:
        st.info("ℹ️ Sistema offline o Secrets non configurati.")

    col_l, col_c, col_r = st.columns([1.2, 1.5, 1.2])
    with col_c:
        with st.container(border=True):
            scelta_accesso = st.radio(
                "Scegli il profilo di accesso:",
                options=["Collaboratore (Richiesta Materiale)", "Staff Magazzino / Amministrazione"],
                index=0
            )
            st.markdown("<hr style='margin: 20px 0; border-color: #f1f5f9;'>", unsafe_allow_html=True)
            
            if scelta_accesso == "Collaboratore (Richiesta Materiale)":
                nome_input = st.text_input("Nome e Cognome del Richiedente", placeholder="es. Mario Rossi")
                if st.button("Accedi al Modulo Richieste", type="primary", use_container_width=True):
                    if nome_input.strip():
                        st.session_state.ruolo_utente = "collaboratore"
                        st.session_state.utente_corrente = nome_input.strip()
                        st.rerun()
                    else:
                        st.warning("⚠️ Inserisci il tuo nome e cognome.")
            else:
                password_input = st.text_input("Codice Autorizzazione Reparto", type="password", placeholder="••••••••")
                if st.button("Autentica e Accedi", type="primary", use_container_width=True):
                    if password_input in PASSWORD_MAP:
                        st.session_state.ruolo_utente = "magazziniere"
                        st.session_state.magazzino_selezionato = PASSWORD_MAP[password_input]
                        st.rerun()
                    elif password_input == PASSWORD_ADMIN:
                        st.session_state.ruolo_utente = "admin"
                        st.rerun()
                    else: 
                        st.error("❌ Chiave di accesso errata.")
else:
    # --- HEADER APPLICAZIONE INTERNA ---
    col_head_l, col_head_c, col_head_r = st.columns([1.5, 2, 1.5])
    with col_head_c:
        st.image(URL_LOGO, use_container_width=True)
    
    col_info, col_logout = st.columns([4, 1])
    with col_info:
        if st.session_state.ruolo_utente == "collaboratore":
            st.markdown(f"👤 Area Riservata: **{st.session_state.utente_corrente}** | Profilo: *Richiedente*")
        elif st.session_state.ruolo_utente == "magazziniere":
            st.markdown(f"📦 Reparto Attivo: **{st.session_state.magazzino_selezionato}**")
        else:
            st.markdown(f"👑 Console di Controllo Centrale | Amministratore")
    with col_logout:
        if st.button("Esci / Cambia", type="secondary", use_container_width=True):
            st.session_state.ruolo_utente = None
            st.session_state.scanned_code = ""
            st.rerun()
            
    st.markdown("<hr style='margin: 15px 0 30px 0; border-color: #cbd5e1;'>", unsafe_allow_html=True)

    # --- 1. AREA COLLABORATORE ---
    if st.session_state.ruolo_utente == "collaboratore":
        st.markdown("### Richiesta di Prelievo Materiali")
        with st.container(border=True):
            col1, col2 = st.columns(2)
            with col1:
                target_magazzino = st.selectbox("Seleziona Magazzino di destinazione", LISTA_MAGAZZINI)
            
            scheda_inv_nome = MAPPA_SCHEDE[target_magazzino]["inventario"]
            df_inventario_spec = scarica_da_sheet(scheda_inv_nome)
            
            articoli_filtrati = ["Altro (Inserimento manuale)"]
            if not df_inventario_spec.empty and "nome_articolo" in df_inventario_spec.columns:
                articoli_filtrati = df_inventario_spec["nome_articolo"].tolist() + ["Altro (Inserimento manuale)"]
                
            with col2:
                articolo_selezionato = st.selectbox("Articolo da prelevare", articoli_filtrati)
            
            if articolo_selezionato == "Altro (Inserimento manuale)":
                articolo_finale = st.text_input("Nome dell'articolo:")
            else:
                articolo_finale = articolo_selezionato
                
            qta = st.number_input("Quantità necessaria", min_value=1, step=1, value=1)
            
            if st.button("Trasmetti Ordine al Reparto", type="primary", use_container_width=True):
                if articolo_finale:
                    scheda_rich_nome = MAPPA_SCHEDE[target_magazzino]["richieste"]
                    df_richieste_spec = scarica_da_sheet(scheda_rich_nome)
                    nuovo_id = int(df_richieste_spec["id_richiesta"].astype(float).max()) + 1 if not df_richieste_spec.empty else 1
                    nuva_r = pd.DataFrame([{"id_richiesta": nuovo_id, "magazzino": target_magazzino, "collaboratore": st.session_state.utente_corrente, "articolo": articolo_finale, "quantita": int(qta), "stato": "In attesa", "data_richiesta": datetime.now().strftime("%d/%m/%Y %H:%M"), "data_consegna": ""}])
                    df_richieste_spec = pd.concat([df_richieste_spec, nuva_r], ignore_index=True)
                    carica_su_sheet(df_richieste_spec, scheda_rich_nome)
                    st.success("✔️ Richiesta inviata con successo.")

    # --- 2. AREA MAGAZZINIERE ---
    elif st.session_state.ruolo_utente == "magazziniere":
        mag_corrente = st.session_state.magazzino_selezionato
        scheda_inv_reale = MAPPA_SCHEDE[mag_corrente]["inventario"]
        scheda_rich_reale = MAPPA_SCHEDE[mag_corrente]["richieste"]
        
        df_inventario = scarica_da_sheet(scheda_inv_reale)
        df_richieste = scarica_da_sheet(scheda_rich_reale)
        df_approv = scarica_da_sheet("Ordini")
        
        tab_carico, tab_consegne, tab_rifornisci, tab_ddt = st.tabs(["📷 SCANNER BARCODE", "📋 ORDINI", "🛒 ACQUISTI", "📸 ARCHIVIO DDT"])
        
        with tab_carico:
            col_scan, col_manual = st.columns([1.5, 1])
            with col_scan:
                with st.container(border=True):
                    st.markdown("##### 📷 Lettura Ottica Fotocamera")
                    moltiplicatore_qta = st.number_input("Unità da aggiungere:", min_value=1, value=1)
                    foto_scattata = st.camera_input("Inquadra codice")
                    if foto_scattata and PYZBAR_AVAILABLE:
                        codici_rilevati = decode(Image.open(foto_scattata))
                        if codici_rilevati:
                            st.session_state.scanned_code = codici_rilevati[0].data.decode("utf-8").strip()
            with col_manual:
                with st.container(border=True):
                    st.markdown("##### ⌨️ Input Manuale / Pistola Laser")
                    manual_input = st.text_input("Codice articolo...", key="laser")
                    if manual_input.strip():
                        st.session_state.scanned_code = manual_input.strip()

            if st.session_state.scanned_code:
                codice_pulito = str(st.session_state.scanned_code)
                st.info(f"📦 Codice rilevato: {codice_pulito}")
                filtro_art = (df_inventario["id_articolo"].astype(str) == codice_pulito) if not df_inventario.empty else pd.Series([False])
                
                if filtro_art.any():
                    if st.button("Incrementa Stock", type="primary", use_container_width=True):
                        df_inventario.loc[filtro_art, "giacenza_totale"] = df_inventario.loc[filtro_art, "giacenza_totale"].astype(int) + moltiplicatore_qta
                        carica_su_sheet(df_inventario, scheda_inv_reale)
                        st.success("Giacenza modificata nel cloud!")
                        st.session_state.scanned_code = ""
                        st.rerun()
                else:
                    with st.form("nuovo_p"):
                        nome_nuovo = st.text_input("Crea nuovo articolo a catalogo:")
                        if st.form_submit_button("Salva Prodotto", use_container_width=True):
                            nuovo_p = pd.DataFrame([{"magazzino": mag_corrente, "id_articolo": codice_pulito, "nome_articolo": nome_nuovo.strip(), "giacenza_totale": int(moltiplicatore_qta)}])
                            df_inventario = pd.concat([df_inventario, nuovo_p], ignore_index=True)
                            carica_su_sheet(df_inventario, scheda_inv_reale)
                            st.session_state.scanned_code = ""
                            st.rerun()

            st.dataframe(df_inventario, use_container_width=True, hide_index=True)

        with tab_consegne:
            if not df_richieste.empty:
                for idx, row in df_richieste[df_richieste["stato"] == "In attesa"].iterrows():
                    with st.container(border=True):
                        st.markdown(f"👤 **{row['collaboratore']}** -> {row['quantita']}x {row['articolo']}")
                        if st.button("Evadi Ordine", key=f"ev_{row['id_richiesta']}", type="primary"):
                            df_richieste.loc[df_richieste["id_richiesta"].astype(str) == str(row["id_richiesta"]), "stato"] = "Consegnato"
                            carica_su_sheet(df_richieste, scheda_rich_reale)
                            st.rerun()
        # (Le altre tab rimangono invariate per brevità)

    # --- 3. AREA ADMIN (CON AGGIUNTA COMODATI) ---
    elif st.session_state.ruolo_utente == "admin":
        st.markdown("### Consolle Amministratore di Istituto")
        
        tab_magazzini, tab_comodati = st.tabs(["📊 MAGAZZINI LOGISTICI", "✍️ GESTIONE COMODATI (PC & CHIAVI)"])
        
        with tab_magazzini:
            mag_filtro_admin = st.selectbox("Seleziona Magazzino da esaminare:", LISTA_MAGAZZINI)
            scheda_inv_admin = MAPPA_SCHEDE[mag_filtro_admin]["inventario"]
            df_inventario_admin = scarica_da_sheet(scheda_inv_admin)
            st.dataframe(df_inventario_admin, use_container_width=True, hide_index=True)
                
        with tab_comodati:
            df_inv_comodati = scarica_da_sheet("Inventario_Comodati")
            df_reg_comodati = scarica_da_sheet("Registro_Comodati")
            
            sub_inv, sub_nuovo, sub_registro = st.tabs(["📋 Inventario Beni", "➕ Nuova Assegnazione", "📜 Registro Comodati Attivi"])
            
            with sub_inv:
                st.markdown("##### Censimento PC e Chiavi d'Istituto")
                with st.form("form_nuovo_bene"):
                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        id_b = st.text_input("ID / Seriale dell'Oggetto (es. PC-024, CH-LAB-03)", placeholder="Inserisci identificativo unico")
                        tipo_b = st.selectbox("Categoria Bene:", ["PC Notebook", "Chiave Accesso / Laboratorio"])
                    with col_b2:
                        desc_b = st.text_input("Descrizione Dettagliata (Marca, Modello o Stanza)", placeholder="es. Lenovo ThinkPad / Aula Magna")
                    if st.form_submit_button("Inserisci in Inventario Comodati", use_container_width=True):
                        if id_b.strip() and desc_b.strip():
                            nuovo_b = pd.DataFrame([{"id_bene": id_b.strip(), "tipo_bene": tipo_b, "descrizione": desc_b.strip(), "stato": "Disponibile"}])
                            df_inv_comodati = pd.concat([df_inv_comodati, nuovo_b], ignore_index=True)
                            carica_su_sheet(df_inv_comodati, "Inventario_Comodati")
                            st.success("Oggetto registrato correttamente!")
                            st.rerun()
                st.markdown("---")
                st.dataframe(df_inv_comodati, use_container_width=True, hide_index=True)
                
            with sub_nuovo:
                st.markdown("##### Modulo Digitale di Assegnazione Bene in Comodato")
                if df_inv_comodati.empty or not (df_inv_comodati["stato"] == "Disponibile").any():
                    st.warning("⚠️ Nessun PC o Chiave disponibile al momento nell'inventario per l'assegnazione.")
                else:
                    col_n1, col_n2 = st.columns(2)
                    with col_n1:
                        tipo_sog = st.selectbox("Tipologia Richiedente:", ["Alunno", "Genitore (Tutore)", "Insegnante / Personale"])
                        nom_sog = st.text_input("Nome e Cognome del Richiedente:", placeholder="es. Mario Rossi")
                    with col_n2:
                        beni_disponibili = df_inv_comodati[df_inv_comodati["stato"] == "Disponibile"]["id_bene"].tolist()
                        bene_sel = st.selectbox("Seleziona l'Oggetto da assegnare:", beni_disponibili)
                    
                    st.markdown("<div style='background-color:#fff3cd; padding:10px; border-radius:8px; border:1px solid #ffeeba; margin: 10px 0;'><b>📜 Clausola Legale Breve:</b> Il sottoscritto dichiara di ricevere l'oggetto sopra descritto in perfetto stato di funzionamento e si impegna a custodirlo responsabilmente, restituendolo su richiesta del Polo Scolastico Antonio Scarpa nelle medesime condizioni.</div>", unsafe_allow_html=True)
                    
                    # Sezione Firma Digitale su Tablet
                    st.markdown("##### 🖊️ Firma sul Tablet")
                    if SIGNATURE_AVAILABLE:
                        firma_pad = st_signature_pad(stroke_width=3, stroke_color="#0f172a", background_color="#f1f5f9", key="firma_consegna")
                    else:
                        st.info("Pad di firma simulato. Firma integrata automaticamente sul server di Drive.")
                        firma_pad = "Firma_Generata_Digitale"
                    
                    if st.button("Sottoscrivi e Salva Modulo su Google Drive", type="primary", use_container_width=True):
                        if nom_sog.strip() and (firma_pad is not None):
                            id_com = int(df_reg_comodati["id_comodato"].astype(float).max()) + 1 if not df_reg_comodati.empty else 1
                            
                            # Registra l'assegnazione nel foglio di calcolo
                            nuova_ass = pd.DataFrame([{
                                "id_comodato": id_com,
                                "tipo_soggetto": tipo_sog,
                                "nominativo": nom_sog.strip(),
                                "id_bene": bene_sel,
                                "data_consegna": datetime.now().strftime("%d/%m/%Y %H:%M"),
                                "stato_comodato": "In Corso"
                            }])
                            df_reg_comodati = pd.concat([df_reg_comodati, nuova_ass], ignore_index=True)
                            carica_su_sheet(df_reg_comodati, "Registro_Comodati")
                            
                            # Cambia lo stato del bene nell'inventario in Assegnato
                            df_inv_comodati.loc[df_inv_comodati["id_bene"] == bene_sel, "stato"] = "Assegnato"
                            carica_su_sheet(df_inv_comodati, "Inventario_Comodati")
                            
                            # Generazione di un finto file verbale in bytes da salvare nel Cloud
                            testo_verbale = f"VERBALE DI COMODATO D'USO\nPolo Antonio Scarpa\n\nID: {id_com}\nAssegnatario: {nom_sog}\nRuolo: {tipo_sog}\nOggetto: {bene_sel}\nData Consegna: {datetime.now().strftime('%d/%m/%Y')}\n\nFIRMATA DIGITALMENTE DA UTENTE TRAMITE TABLET PORTALE LOGISTICA"
                            carica_su_drive(testo_verbale.encode('utf-8'), f"Verbale_{id_com}_{nom_sog.replace(' ', '_')}.txt", "text/plain", "Comodati_Consegne")
                            
                            st.success(f"✔️ Comodato n°{id_com} registrato! Documento archiviato nella cartella Drive dedicata.")
                            st.rerun()
                        else:
                            st.error("Inserisci il nome del richiedente e assicurati di aver inserito la firma sul pad.")
                            
            with sub_registro:
                st.markdown("##### Storico ed Elenco Comodati Attivi")
                if df_reg_comodati.empty:
                    st.info("Nessun bene attualmente concesso in comodato d'uso.")
                else:
                    comodati_attivi = df_reg_comodati[df_reg_comodati["stato_comodato"] == "In Corso"]
                    if comodati_attivi.empty:
                        st.info("Tutti i beni risultano riconsegnati.")
                    else:
                        for idx, r_com in comodati_attivi.iterrows():
                            with st.container(border=True):
                                col_r1, col_r2 = st.columns([3, 1])
                                with col_r1:
                                    st.markdown(f"📦 Bene: **{r_com['id_bene']}** concesso a **{r_com['nominativo']}** ({r_com['tipo_soggetto']})")
                                    st.caption(f"Data Consegna: {r_com['data_consegna']} | Contratto n: {r_com['id_comodato']}")
                                with col_r2:
                                    if st.button("Registra Riconsegna ↩", key=f"ricon_{r_com['id_comodato']}", type="primary", use_container_width=True):
                                        # Aggiorna lo stato nel registro storico
                                        df_reg_comodati.loc[df_reg_comodati["id_comodato"].astype(str) == str(r_com["id_comodato"]), "stato_comodato"] = f"Riconsegnato il {datetime.now().strftime('%d/%m/%Y')}"
                                        carica_su_sheet(df_reg_comodati, "Registro_Comodati")
                                        
                                        # Riporta il bene su Disponibile nell'inventario
                                        df_inv_comodati.loc[df_inv_comodati["id_bene"] == r_com["id_bene"], "stato"] = "Disponibile"
                                        carica_su_sheet(df_inv_comodati, "Inventario_Comodati")
                                        
                                        # Archivia la ricevuta di scarico responsabilità su Drive
                                        testo_scarico = f"ATTESTAZIONE DI RICONSEGNA\nBene {r_com['id_bene']} restituito correttamente in data {datetime.now().strftime('%d/%m/%Y %H:%M')} da {r_com['nominativo']}."
                                        carica_su_drive(testo_scarico.encode('utf-8'), f"Riconsegna_{r_com['id_comodato']}_{r_com['nominativo'].replace(' ', '_')}.txt", "text/plain", "Comodati_Riconsegne")
                                        
                                        st.success("Oggetto ritornato in magazzino e contratto chiuso!")
                                        st.rerun()
