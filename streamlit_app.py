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
        /* Sfondo dell'intera applicazione */
        .stApp {
            background-color: #f8fafc;
        }
        
        /* Personalizzazione dei box e dei container (Card) */
        [data-testid="stVerticalBlockBorderWrapper"] {
            background: white !important;
            padding: 30px !important;
            border-radius: 16px !important;
            border: 1px solid #e2e8f0 !important;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.05) !important;
        }
        
        /* Pulsante primario personalizzato con il rosso istituzionale */
        div.stButton > button:first-child {
            background-color: #8b1e1e !important;
            color: white !important;
            border-radius: 10px !important;
            border: none !important;
            font-weight: 600 !important;
            padding: 12px 24px !important;
            box-shadow: 0 4px 6px -1px rgba(139, 30, 30, 0.2) !important;
            transition: all 0.2s ease-in-out !important;
        }
        
        /* Effetto hover pulsante primario */
        div.stButton > button:first-child:hover {
            background-color: #a72828 !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 6px 12px -2px rgba(139, 30, 30, 0.3) !important;
        }
        
        /* Inputs estetici più puliti */
        .stTextInput input, .stSelectbox div[data-baseweb="select"] {
            border-radius: 10px !important;
            border: 1px solid #cbd5e1 !important;
        }
        
        /* Titoli e testo */
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
            if "Inventario" in nome_scheda:
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

# --- FUNZIONE DRIVE PER I DDT ---
def carica_su_drive(file_bytes, nome_file, mime_type, nome_magazzino):
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
        nome_sottocartella = f"DDT_{nome_magazzino.replace(' ', '_')}"
        query = f"name='{nome_sottocartella}' and '{ID_CARTELLA_DRIVE_PRINCIPALE}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        risultato = service.files().list(q=query, spaces='drive', supportsAllDrives=True, includeItemsFromTrashed=False).execute()
        files = risultato.get('files', [])
        
        id_cartella = files[0]['id'] if files else service.files().create(body={'name': nome_sottocartella, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [ID_CARTELLA_DRIVE_PRINCIPALE]}, fields='id', supportsAllDrives=True).execute().get('id')
        
        meta_file = {'name': nome_file, 'parents': [id_cartella]}
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)
        service.files().create(body=meta_file, media_body=media, fields='id', supportsAllDrives=True).execute()
        return True
    except Exception:
        return None

# Controllo iniziale della presenza dei Secrets per avvisare l'amministratore in modo elegante
fogli_connessi = connetti_google_sheets() is not None

# Stato sessione iniziale
if "ruolo_utente" not in st.session_state: st.session_state.ruolo_utente = None
if "utente_corrente" not in st.session_state: st.session_state.utente_corrente = ""
if "magazzino_selezionato" not in st.session_state: st.session_state.magazzino_selezionato = None
if "scanned_code" not in st.session_state: st.session_state.scanned_code = ""

# --- INTERFACCIA DI ACCESSO ---
if st.session_state.ruolo_utente is None:
    # Centratura e correzione formattazione immagine ('use_container_width')
    col_logo_l, col_logo_c, col_logo_r = st.columns([1, 1.8, 1])
    with col_logo_c:
        st.image(URL_LOGO, use_container_width=True)
        st.markdown("<h2 style='text-align: center; margin-top: 15px; margin-bottom: 5px;'>Piattaforma Logistica Integrata</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #64748b; font-size: 1.1rem; margin-bottom: 30px;'>Gestione Inventario & Rifornimenti d'Istituto</p>", unsafe_allow_html=True)
    
    # Se il cloud di Streamlit non è configurato con le chiavi Google, mostra un avviso pulito anziché crashare
    if not fogli_connessi:
        st.info("ℹ️ Il sistema è in modalità offline o le credenziali Google Cloud (`google_creds`) non sono ancora state inserite nel pannello Secrets di Streamlit Cloud.")

    # Finestra di Login centrata e proporzionata con ombreggiature
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
                st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
                if st.button("Accedi al Modulo Richieste", type="primary", use_container_width=True):
                    if nome_input.strip():
                        st.session_state.ruolo_utente = "collaboratore"
                        st.session_state.utente_corrente = nome_input.strip()
                        st.rerun()
                    else:
                        st.warning("⚠️ Inserisci il tuo nome e cognome per procedere.")
            else:
                password_input = st.text_input("Codice Autorizzazione Reparto", type="password", placeholder="••••••••")
                st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
                if st.button("Autentica e Accedi", type="primary", use_container_width=True):
                    if password_input in PASSWORD_MAP:
                        st.session_state.ruolo_utente = "magazziniere"
                        st.session_state.magazzino_selezionato = PASSWORD_MAP[password_input]
                        st.rerun()
                    elif password_input == PASSWORD_ADMIN:
                        st.session_state.ruolo_utente = "admin"
                        st.rerun()
                    else: 
                        st.error("❌ Chiave di accesso non riconosciuta dal sistema.")
else:
    # --- HEADER APPLICAZIONE INTERNA ---
    col_head_l, col_head_c, col_head_r = st.columns([1.5, 2, 1.5])
    with col_head_c:
        st.image(URL_LOGO, use_container_width=True)
    
    # Barra informativa di stato utente
    col_info, col_logout = st.columns([4, 1])
    with col_info:
        if st.session_state.ruolo_utente == "collaboratore":
            st.markdown(f"👤 Area Riservata: **{st.session_state.utente_corrente}** | Profilo: *Richiedente*")
        elif st.session_state.ruolo_utente == "magazziniere":
            st.markdown(f"📦 Reparto Attivo: **{st.session_state.magazzino_selezionato}** | Operatore Logistico")
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
                articolo_finale = st.text_input("Nome dell'articolo non presente in lista:")
            else:
                articolo_finale = articolo_selezionato
                
            qta = st.number_input("Quantità necessaria", min_value=1, step=1, value=1)
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Trasmetti Ordine al Reparto", type="primary", use_container_width=True):
                if not fogli_connessi:
                    st.error("Sincronizzazione non disponibile: il database Google Sheets non è connesso.")
                elif articolo_finale:
                    scheda_rich_nome = MAPPA_SCHEDE[target_magazzino]["richieste"]
                    df_richieste_spec = scarica_da_sheet(scheda_rich_nome)
                    
                    nuovo_id = int(df_richieste_spec["id_richiesta"].astype(float).max()) + 1 if not df_richieste_spec.empty else 1
                    nuva_r = pd.DataFrame([{"id_richiesta": nuovo_id, "magazzino": target_magazzino, "collaboratore": st.session_state.utente_corrente, "articolo": articolo_finale, "quantita": int(qta), "stato": "In attesa", "data_richiesta": datetime.now().strftime("%d/%m/%Y %H:%M"), "data_consegna": ""}])
                    
                    df_richieste_spec = pd.concat([df_richieste_spec, nuva_r], ignore_index=True)
                    carica_su_sheet(df_richieste_spec, scheda_rich_nome)
                    st.success("✔️ Richiesta inviata. Monitora lo stato con il personale di reparto.")
                else:
                    st.error("Specificare il nome del materiale.")

    # --- 2. AREA MAGAZZINIERE ---
    elif st.session_state.ruolo_utente == "magazziniere":
        mag_corrente = st.session_state.magazzino_selezionato
        
        scheda_inv_reale = MAPPA_SCHEDE[mag_corrente]["inventario"]
        scheda_rich_reale = MAPPA_SCHEDE[mag_corrente]["richieste"]
        
        df_inventario = scarica_da_sheet(scheda_inv_reale)
        df_richieste = scarica_da_sheet(scheda_rich_reale)
        df_approv = scarica_da_sheet("Ordini")
        
        tab_carico, tab_consegne, tab_rifornisci, tab_ddt = st.tabs([
            "📷 SCANNER BARCODE", 
            "📋 ORDINI COLLABORATORI", 
            "🛒 ORDINI DI ACQUISTO", 
            "📸 ARCHIVIO DDT"
        ])
        
        with tab_carico:
            col_scan, col_manual = st.columns([1.5, 1])
            
            with col_scan:
                with st.container(border=True):
                    st.markdown("##### 📷 Lettura Ottica Fotocamera")
                    moltiplicatore_qta = st.number_input("Unità da aggiungere al codice rilevato:", min_value=1, value=1)
                    
                    foto_scattata = st.camera_input("Inquadra codice a barre")
                    if foto_scattata and PYZBAR_AVAILABLE:
                        try:
                            codici_rilevati = decode(Image.open(foto_scattata))
                            if codici_rilevati:
                                st.session_state.scanned_code = codici_rilevati[0].data.decode("utf-8").strip()
                            else:
                                st.warning("Nessun codice trovato nell'inquadratura.")
                        except Exception as e:
                            st.error(f"Errore scanner: {e}")
            
            with col_manual:
                with st.container(border=True):
                    st.markdown("##### ⌨️ Lettore Laser USB / Input Manuale")
                    manual_input = st.text_input("Spara il codice col lettore o digitalo:", placeholder="Codice seriale...")
                    if manual_input.strip():
                        st.session_state.scanned_code = manual_input.strip()

            if st.session_state.scanned_code:
                codice_pulito = str(st.session_state.scanned_code)
                st.markdown(f"<div style='background-color: #f0fdf4; padding: 15px; border-radius: 10px; border: 1px solid #bbf7d0; margin: 15px 0;'>📦 <b>Codice Attivo:</b> {codice_pulito}</div>", unsafe_allow_html=True)
                
                filtro_art = (df_inventario["id_articolo"].astype(str) == codice_pulito) if not df_inventario.empty else pd.Series([False])
                
                if filtro_art.any():
                    if st.button(f"Incrementa Giacenza (+ {moltiplicatore_qta})", type="primary", use_container_width=True):
                        df_inventario.loc[filtro_art, "giacenza_totale"] = df_inventario.loc[filtro_art, "giacenza_totale"].astype(int) + moltiplicatore_qta
                        carica_su_sheet(df_inventario, scheda_inv_reale)
                        st.success("Giacenza aggiornata nel Cloud Sheet!")
                        st.session_state.scanned_code = ""
                        st.rerun()
                else:
                    st.warning("Articolo non censito nel database di questo reparto. Registrazione rapida:")
                    with st.form("nuovo_prodotto_form"):
                        nome_nuovo = st.text_input("Nome / Descrizione nuovo articolo:")
                        if st.form_submit_button("Crea Articolo e Carica Stock", use_container_width=True):
                            if nome_nuovo.strip():
                                nuovo_p = pd.DataFrame([{"magazzino": mag_corrente, "id_articolo": codice_pulito, "nome_articolo": nome_nuovo.strip(), "giacenza_totale": int(moltiplicatore_qta)}])
                                df_inventario = pd.concat([df_inventario, nuovo_p], ignore_index=True)
                                carica_su_sheet(df_inventario, scheda_inv_reale)
                                st.success("Prodotto registrato a catalogo!")
                                st.session_state.scanned_code = ""
                                st.rerun()

            st.markdown("<br><h5>📦 Giacenze di Reparto Correnti</h5>", unsafe_allow_html=True)
            if not df_inventario.empty:
                st.dataframe(df_inventario, use_container_width=True, hide_index=True)
            else:
                st.info("In attesa di dati o connessione al database Google Sheets.")

        with tab_consegne:
            st.markdown("##### 📋 Richieste Personale d'Istituto")
            if not df_richieste.empty and "stato" in df_richieste.columns:
                richieste_mie = df_richieste[df_richieste["stato"] == "In attesa"]
                if richieste_mie.empty: 
                    st.info("Nessun ordine in sospeso da evadere.")
                else:
                    for idx, row in richieste_mie.iterrows():
                        with st.container(border=True):
                            col_testo, col_azione = st.columns([3, 1])
                            with col_testo:
                                st.markdown(f"👤 **{row['collaboratore']}** richiede **{row['quantita']}** pz. di **{row['articolo']}**")
                                st.caption(f"Inviata il: {row['data_richiesta']}")
                            with col_azione:
                                if st.button("Approva ed Evadi", key=f"ev_{row['id_richiesta']}", type="primary", use_container_width=True):
                                    filtro = (df_inventario["nome_articolo"] == row['articolo'])
                                    if filtro.any() and int(df_inventario.loc[filtro, "giacenza_totale"].values[0]) >= int(row['quantita']):
                                        df_inventario.loc[filtro, "giacenza_totale"] = int(df_inventario.loc[filtro, "giacenza_totale"].values[0]) - int(row['quantita'])
                                        df_richieste.loc[df_richieste["id_richiesta"].astype(str) == str(row["id_richiesta"]), "stato"] = "Consegnato"
                                        df_richieste.loc[df_richieste["id_richiesta"].astype(str) == str(row["id_richiesta"]), "data_consegna"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                                        
                                        carica_su_sheet(df_inventario, scheda_inv_reale)
                                        carica_su_sheet(df_richieste, scheda_rich_reale)
                                        st.rerun()
                                    else: 
                                        st.error("Impossibile evadere: scorte insufficienti a magazzino.")

        with tab_rifornisci:
            st.markdown("##### 🛒 Segnalazione Mancanza Beni all'Amministrazione")
            with st.container(border=True):
                mat_urgente = st.text_input("Articolo o bene esaurito:")
                qta_urgente = st.number_input("Quantità pacchi/scatole ordinarie:", min_value=1, step=1, value=1)
                if st.button("Inoltra Flusso Acquisti", type="primary", use_container_width=True):
                    if mat_urgente.strip():
                        nuovo_id_a = int(df_approv["id_acquisto"].astype(float).max()) + 1 if not df_approv.empty else 1
                        nuovo_o = pd.DataFrame([{"id_acquisto": nuovo_id_a, "magazzino": mag_corrente, "articolo": mat_urgente.strip(), "quantita_richiesta": int(qta_urgente), "stato": "In attesa", "data_richiesta": datetime.now().strftime("%d/%m/%Y %H:%M")}])
                        df_approv = pd.concat([df_approv, nuovo_o], ignore_index=True)
                        carica_su_sheet(df_approv, "Ordini")
                        st.success("Richiesta d'acquisto inserita nel pannello Admin.")
                    else:
                        st.error("Inserire la descrizione del materiale esaurito.")

        with tab_ddt:
            st.markdown("##### 📸 Archiviazione Digitale Documenti di Trasporto")
            with st.container(border=True):
                file_ddt = st.file_uploader("Upload o Scatto Foto Documento Fiscale (DDT)", type=["png", "jpg", "jpeg", "pdf"])
                fornitore = st.text_input("Ditta / Fornitore:")
                if file_ddt and st.button("Salva in Cloud Drive", type="primary", use_container_width=True):
                    if fornitore.strip():
                        nome_f = f"DDT_{mag_corrente.replace(' ', '_')}_{fornitore.strip()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                        if carica_su_drive(file_ddt.getvalue(), nome_f, file_ddt.type, mag_corrente):
                            st.success("Documento indicizzato e archiviato su Google Drive.")
                    else:
                        st.error("Specificare la ditta fornitrice.")

    # --- 3. AREA ADMIN ---
    elif st.session_state.ruolo_utente == "admin":
        st.markdown("### Consolle Amministratore di Istituto")
        
        mag_filtro_admin = st.selectbox("Seleziona Magazzino da esaminare:", LISTA_MAGAZZINI)
        
        tab_st, tab_ac = st.tabs(["📊 ANALISI GIACENZE", "⚖️ RICHIESTE DI ACQUISTO"])
        
        with tab_st:
            scheda_inv_admin = MAPPA_SCHEDE[mag_filtro_admin]["inventario"]
            df_inventario_admin = scarica_da_sheet(scheda_inv_admin)
            st.markdown(f"Giacenze per scheda: **{scheda_inv_admin}**")
            if not df_inventario_admin.empty:
                st.dataframe(df_inventario_admin.sort_values(by="nome_articolo"), use_container_width=True, hide_index=True)
            else:
                st.info("Nessun articolo caricato o database non connesso.")
                
        with tab_ac:
            df_approv_admin = scarica_da_sheet("Ordini")
            if not df_approv_admin.empty and "stato" in df_approv_admin.columns:
                pendenti = df_approv_admin[(df_approv_admin["stato"] == "In attesa") & (df_approv_admin["magazzino"] == mag_filtro_admin)]
                if pendenti.empty: 
                    st.info("Nessun ordine di acquisto da deliberare per questo reparto.")
                else:
                    for idx, row in pendenti.iterrows():
                        with st.container(border=True):
                            c_t, c_b = st.columns([3, 1])
                            with c_t:
                                st.markdown(f"🏢 Il reparto **{row['magazzino']}** ha esaurito:")
                                st.markdown(f"#### {row['quantita_richiesta']}x {row['articolo']}")
                                st.caption(f"Inviato il: {row['data_richiesta']}")
                            with c_b:
                                if st.button("Autorizza Acquisto", key=f"ap_ad_{row['id_acquisto']}", type="primary", use_container_width=True):
                                    df_approv_admin.loc[df_approv_admin["id_acquisto"].astype(str) == str(row["id_acquisto"]), "stato"] = "Approvato"
                                    carica_su_sheet(df_approv_admin, "Ordini")
                                    
                                    sch_inv_dest = MAPPA_SCHEDE[row["magazzino"]]["inventario"]
                                    df_inv_dest = scarica_da_sheet(sch_inv_dest)
                                    
                                    filtro = (df_inv_dest["nome_articolo"] == row["articolo"]) if not df_inv_dest.empty else pd.Series([False])
                                    if filtro.any():
                                        df_inv_dest.loc[filtro, "giacenza_totale"] = df_inv_dest.loc[filtro, "giacenza_totale"].astype(int) + int(row["quantita_richiesta"])
                                    else:
                                        nuovo_p = pd.DataFrame([{"magazzino": row["magazzino"], "id_articolo": f"NEW_{row['id_acquisto']}", "nome_articolo": row["articolo"], "giacenza_totale": int(row["quantita_richiesta"])}])
                                        df_inv_dest = pd.concat([df_inv_dest, nuovo_p], ignore_index=True)
                                    
                                    carica_su_sheet(df_inv_dest, sch_inv_dest)
                                    st.rerun()
