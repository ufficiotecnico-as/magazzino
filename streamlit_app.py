import streamlit as st
import pandas as pd
from datetime import datetime
import io
import os
from PIL import Image

# Libreria per Google Sheets
try:
    import gspread
    from google.oauth2 import service_account
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

# Importiamo pyzbar per i codici a barre
try:
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

PASSWORD_MAP = {
    "ata2026": "Personale ATA",
    "officina2026": "Officina",
    "tecnici2026": "Tecnici Informatici"
}
PASSWORD_ADMIN = "admin99"

URL_LOGO = "https://cspace.spaggiari.eu//pub/TVII0004/TVII0004-intestazione-nuova-senzaloghi.png?_t=1712923868"
ID_CARTELLA_DRIVE_PRINCIPALE = "1bVTs2smvVJONs2oIAFZdDvX9pYDK9MZT"
SPREADSHEET_ID = "1Q91H_TULvpsnPcyOwQ1lxmjOf809xp4cUz9p1EdMc-4"
LISTA_MAGAZZINI = ["Personale ATA", "Officina", "Tecnici Informatici"]

st.set_page_config(page_title="Gestione Magazzini Scarpa", page_icon="🧺", layout="wide")

# --- CONNESSIONE A GOOGLE SHEETS ---
@st.cache_resource(ttl=60)
def connetti_google_sheets():
    if not GSPREAD_AVAILABLE or "google_creds" not in st.secrets:
        return None
    try:
        creds_dict = dict(st.secrets["google_creds"])
        if "\\n" in creds_dict["private_key"]:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        return client.open_by_key(SPREADSHEET_ID)
    except Exception as e:
        st.error(f"Errore di connessione a Google Sheets: {e}")
        return None

# --- FUNZIONI DI LETTURA / SCRITTURA ---
def scarica_da_sheet(nome_scheda):
    sh = connetti_google_sheets()
    if sh:
        try:
            worksheet = sh.worksheet(nome_scheda)
            records = worksheet.get_all_records()
            return pd.DataFrame(records)
        except Exception:
            # Se la scheda non esiste o è vuota, restituisce un DF vuoto con colonne base
            if nome_scheda == "Inventario":
                return pd.DataFrame(columns=["magazzino", "id_articolo", "nome_articolo", "giacenza_totale"])
            elif nome_scheda == "Richieste":
                return pd.DataFrame(columns=["id_richiesta", "magazzino", "collaboratore", "articolo", "quantita", "stato", "data_richiesta", "data_consegna"])
            else:
                return pd.DataFrame(columns=["id_acquisto", "magazzino", "articolo", "quantita_richiesta", "stato", "data_richiesta"])
    return pd.DataFrame()

def carica_su_sheet(df, nome_scheda):
    sh = connetti_google_sheets()
    if sh:
        try:
            try:
                worksheet = sh.worksheet(nome_scheda)
            except gspread.exceptions.WorksheetNotFound:
                worksheet = sh.add_worksheet(title=nome_scheda, rows="100", cols="20")
            
            worksheet.clear()
            # Sostituisce i valori NaN/Nulli per evitare errori JSON
            df_pulito = df.fillna("")
            worksheet.update([df_pulito.columns.values.tolist()] + df_pulito.values.tolist())
        except Exception as e:
            st.error(f"Impossibile aggiornare Google Sheets: {e}")

# Inizializzazione dati in session_state prelevandoli da Google Sheet
if "db_inventario" not in st.session_state or st.sidebar.button("🔄 Forza Sincronizzazione Fogli Google"):
    st.session_state.db_inventario = scarica_da_sheet("Inventario")
    st.session_state.db_richieste = scarica_da_sheet("Richieste")
    st.session_state.db_approvvigionamenti = scarica_da_sheet("Ordini")

# --- FUNZIONE CARICAMENTO COPIE DDT SU DRIVE ---
def carica_su_drive(file_bytes, nome_file, mime_type, nome_magazzino):
    if not GOOGLE_DRIVE_AVAILABLE or "google_creds" not in st.secrets: 
        return None
    try:
        creds_dict = dict(st.secrets["google_creds"])
        if "\\n" in creds_dict["private_key"]:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=['https://www.googleapis.com/auth/drive'])
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
    except Exception as e:
        st.error(f"Errore nell'invio del file a Drive: {e}")
        return None

if "ruolo_utente" not in st.session_state: st.session_state.ruolo_utente = None
if "utente_corrente" not in st.session_state: st.session_state.utente_corrente = ""
if "magazzino_selezionato" not in st.session_state: st.session_state.magazzino_selezionato = None
if "scanned_code" not in st.session_state: st.session_state.scanned_code = ""

# --- STILE UX/UI ---
st.markdown("""
    <style>
        .stApp { background-color: #f1f5f9 !important; color: #0f172a !important; font-family: 'Inter', sans-serif; }
        [data-testid="stMainBlockContainer"] { max-width: 1150px; margin: 0 auto; padding-top: 2rem; }
        h1 { color: #0f172a !important; font-family: 'Montserrat', sans-serif; font-weight: 800 !important; text-align: center; margin-bottom: 30px !important; }
        h2, h3, h4, label, [data-testid="stWidgetLabel"] p { color: #1e293b !important; font-weight: 700 !important; }
        [data-testid="stContainer"] { background-color: #ffffff !important; border: 1px solid #e2e8f0 !important; border-radius: 16px !important; padding: 28px !important; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important; margin-bottom: 20px; }
        div.stButton > button:first-child { background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%) !important; color: #ffffff !important; border-radius: 10px !important; border: none !important; padding: 12px 24px !important; font-weight: 600 !important; width: 100%; }
        [data-testid="stSidebar"] { background-color: #ffffff !important; border-right: 1px solid #e2e8f0; }
        footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- INTERFACCIA LOGIN ---
if st.session_state.ruolo_utente is None:
    st.image(URL_LOGO, use_container_width=True)
    st.markdown("<h1>Gestione Magazzini Centralizzata</h1>", unsafe_allow_html=True)
    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        with st.container():
            scelta_accesso = st.radio("", ["Sono un Collaboratore (Fai una Richiesta)", "Sono un Magazziniere / Admin"], label_visibility="collapsed")
            if scelta_accesso == "Sono un Collaboratore (Fai una Richiesta)":
                nome_input = st.text_input("Inserisci il tuo Nome e Cognome:")
                if st.button("Accedi all'area Richieste"):
                    if nome_input.strip():
                        st.session_state.ruolo_utente = "collaboratore"
                        st.session_state.utente_corrente = nome_input.strip()
                        st.rerun()
            else:
                password_input = st.text_input("Password di sblocco:", type="password")
                if st.button("Verifica Credenziali"):
                    if password_input in PASSWORD_MAP:
                        st.session_state.ruolo_utente = "magazziniere"
                        st.session_state.magazzino_selezionato = PASSWORD_MAP[password_input]
                        st.rerun()
                    elif password_input == PASSWORD_ADMIN:
                        st.session_state.ruolo_utente = "admin"
                        st.rerun()
                    else: st.error("❌ Password errata.")
else:
    st.image(URL_LOGO, use_container_width=True)
    df_inventario = st.session_state.db_inventario
    df_richieste = st.session_state.db_richieste
    df_approv = st.session_state.db_approvvigionamenti

    with st.sidebar:
        st.markdown(f"<h3>🧺 Area {st.session_state.ruolo_utente.upper()}</h3>", unsafe_allow_html=True)
        if st.session_state.ruolo_utente == "magazziniere": st.info(f"📍 Magazzino: **{st.session_state.magazzino_selezionato}**")
        if st.button("🔒 Esci / Cambia Utente"):
            st.session_state.ruolo_utente = None
            st.session_state.scanned_code = ""
            st.rerun()

    # --- AREA COLLABORATORE ---
    if st.session_state.ruolo_utente == "collaboratore":
        st.markdown(f"<h1>👋 Benvenuto, {st.session_state.utente_corrente}</h1>", unsafe_allow_html=True)
        with st.container():
            target_magazzino = st.selectbox("A quale magazzino vuoi inviare la richiesta?", LISTA_MAGAZZINI)
            
            articoli_filtrati = ["Altro..."]
            if not df_inventario.empty and "magazzino" in df_inventario.columns:
                articoli_filtrati = df_inventario[df_inventario["magazzino"] == target_magazzino]["nome_articolo"].tolist() + ["Altro..."]
                
            articolo_selezionato = st.selectbox("Seleziona cosa ti serve:", articoli_filtrati)
            articolo_finale = st.text_input("Specifica il materiale a mano:") if articolo_selezionato == "Altro..." else articolo_selezionato
            qta = st.number_input("Quantità necessaria:", min_value=1, step=1)
            
            if st.button("Invia Ordine in Magazzino"):
                nuovo_id = int(df_richieste["id_richiesta"].max()) + 1 if not df_richieste.empty else 1
                nuova_r = pd.DataFrame([{"id_richiesta": nuovo_id, "magazzino": target_magazzino, "collaboratore": st.session_state.utente_corrente, "articolo": articolo_finale, "quantita": int(qta), "stato": "In attesa", "data_richiesta": datetime.now().strftime("%d/%m/%Y %H:%M"), "data_consegna": ""}])
                st.session_state.db_richieste = pd.concat([df_richieste, nuova_r], ignore_index=True)
                carica_su_sheet(st.session_state.db_richieste, "Richieste")
                st.success("✔️ Richiesta salvata sul Cloud di Google Sheets!")

    # --- AREA MAGAZZINIERE ---
    elif st.session_state.ruolo_utente == "magazziniere":
        mag_corrente = st.session_state.magazzino_selezionato
        st.markdown(f"<h1>🚚 Pannello Operativo: {mag_corrente}</h1>", unsafe_allow_html=True)
        
        tab_carico, tab_consegne, tab_rifornisci, tab_ddt = st.tabs(["📷 SCANNER REAL-TIME", "📋 Richieste", "🛒 Ordini", "📸 DDT"])
        
        with tab_carico:
            st.markdown("### 🎯 Scatta una foto al Codice a Barre")
            moltiplicatore_qta = st.number_input("Pezzi da aggiungere a ogni scansione:", min_value=1, value=1, step=1)
            
            foto_scattata = st.camera_input("Inquadra il codice da vicino (orizzontale) e scatta")
            if foto_scattata and PYZBAR_AVAILABLE:
                try:
                    img = Image.open(foto_scattata)
                    codici_rilevati = decode(img)
                    if codici_rilevati:
                        st.session_state.scanned_code = codici_rilevati[0].data.decode("utf-8").strip()
                    else:
                        st.error("❌ Codice non rilevato. Riprova tenendolo fermo o migliorando la luce.")
                except Exception as e:
                    st.error(f"Errore decodifica: {e}")

            manual_input = st.text_input("O inserisci manualmente il codice (Tastiera o Pistola USB):")
            if manual_input.strip():
                st.session_state.scanned_code = manual_input.strip()

            if st.session_state.scanned_code:
                codice_pulito = str(st.session_state.scanned_code)
                st.markdown(f"📥 **Codice identificato:** `{codice_pulito}`")
                
                filtro_art = (df_inventario["id_articolo"].astype(str) == codice_pulito) & (df_inventario["magazzino"] == mag_corrente) if not df_inventario.empty else pd.Series([False])
                
                if filtro_art.any():
                    st.session_state.db_inventario.loc[filtro_art, "giacenza_totale"] += moltiplicatore_qta
                    carica_su_sheet(st.session_state.db_inventario, "Inventario")
                    st.success("✔️ Giacenza aggiornata direttamente su Google Sheets!")
                    if st.button("🔄 Prossima scansione"):
                        st.session_state.scanned_code = ""
                        st.rerun()
                else:
                    st.warning("🆕 Codice non presente nel catalogo di questo reparto. Censiscilo:")
                    with st.form("veloce_censimento"):
                        nome_nuovo = st.text_input("Nome Articolo:")
                        if st.form_submit_button("Salva Prodotto"):
                            if nome_nuovo.strip():
                                nuovo_p = pd.DataFrame([{"magazzino": mag_corrente, "id_articolo": codice_pulito, "nome_articolo": nome_nuovo.strip(), "giacenza_totale": int(moltiplicatore_qta)}])
                                st.session_state.db_inventario = pd.concat([df_inventario, nuovo_p], ignore_index=True)
                                carica_su_sheet(st.session_state.db_inventario, "Inventario")
                                st.success("✔️ Salvato!")
                                st.session_state.scanned_code = ""
                                st.rerun()

            st.write("---")
            st.markdown("#### 📦 Inventario Reparto")
            if not df_inventario.empty and "magazzino" in df_inventario.columns:
                st.dataframe(df_inventario[df_inventario["magazzino"] == mag_corrente], use_container_width=True, hide_index=True)

        # --- ALTRE OPERAZIONI MAGAZZINIERE ---
        with tab_consegne:
            if not df_richieste.empty and "stato" in df_richieste.columns:
                richieste_mie = df_richieste[(df_richieste["stato"] == "In attesa") & (df_richieste["magazzino"] == mag_corrente)]
                if richieste_mie.empty: st.info("Nessuna richiesta in attesa.")
                for idx, row in richieste_mie.iterrows():
                    with st.container():
                        st.write(f"👤 **{row['collaboratore']}** richiede {row['quantita']}x {row['articolo']}")
                        if st.button("Segna come Consegnato ✔", key=f"ev_{row['id_richiesta']}"):
                            filtro = (df_inventario["nome_articolo"] == row['articolo']) & (df_inventario["magazzino"] == mag_corrente)
                            if filtro.any() and df_inventario.loc[filtro, "giacenza_totale"].values[0] >= row['quantita']:
                                st.session_state.db_inventario.loc[filtro, "giacenza_totale"] -= row['quantita']
                                st.session_state.db_richieste.loc[st.session_state.db_richieste["id_richiesta"] == row["id_richiesta"], "stato"] = "Consegnato"
                                st.session_state.db_richieste.loc[st.session_state.db_richieste["id_richiesta"] == row["id_richiesta"], "data_consegna"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                                carica_su_sheet(st.session_state.db_inventario, "Inventario")
                                carica_su_sheet(st.session_state.db_richieste, "Richieste")
                                st.rerun()
                            else: st.error("Errore: Stock insufficiente nel foglio Google!")

        with tab_rifornisci:
            mat_urgente = st.text_input("Nome materiale mancante:")
            qta_urgente = st.number_input("Q.tà:", min_value=1, step=1)
            if st.button("Invia ad Admin"):
                nuovo_id_a = int(df_approv["id_acquisto"].max()) + 1 if not df_approv.empty else 1
                nuovo_o = pd.DataFrame([{"id_acquisto": nuovo_id_a, "magazzino": mag_corrente, "articolo": mat_urgente, "quantita_richiesta": int(qta_urgente), "stato": "In attesa", "data_richiesta": datetime.now().strftime("%d/%m/%Y %H:%M")}])
                st.session_state.db_approvvigionamenti = pd.concat([df_approv, nuovo_o], ignore_index=True)
                carica_su_sheet(st.session_state.db_approvvigionamenti, "Ordini")
                st.success("Richiesta inviata all'Admin e salvata sul foglio!")

        with tab_ddt:
            file_ddt = st.file_uploader("Carica foto o PDF del DDT", type=["png", "jpg", "jpeg", "pdf"])
            fornitore = st.text_input("Nome Fornitore:")
            if file_ddt and st.button("Salva ed Invia a Drive"):
                nome_f = f"DDT_{mag_corrente}_{fornitore}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                if carica_su_drive(file_ddt.getvalue(), nome_f, file_ddt.type, mag_corrente):
                    st.success("File archiviato con successo nella cartella condivisa di Drive!")

    # --- AREA ADMIN ---
    elif st.session_state.ruolo_utente == "admin":
        st.markdown("<h1>👑 Pannello di Controllo Amministratore</h1>", unsafe_allow_html=True)
        
        # Filtro rapido ordinato per magazzino nel pannello admin
        mag_filtro_admin = st.selectbox("Filtra visualizzazione dati per reparto:", ["Tutti"] + LISTA_MAGAZZINI)
        
        tab_st, tab_ac = st.tabs(["📊 Stato Scorte (Ordinato)", "🛒 Richieste d'Acquisto Reparti"])
        
        with tab_st:
            if not df_inventario.empty:
                df_mostrato = df_inventario if mag_filtro_admin == "Tutti" else df_inventario[df_inventario["magazzino"] == mag_filtro_admin]
                # Ordina l'inventario per magazzino e poi per nome articolo
                df_mostrato = df_mostrato.sort_values(by=["magazzino", "nome_articolo"])
                st.dataframe(df_mostrato, use_container_width=True, hide_index=True)
            else:
                st.info("Nessun articolo registrato nel foglio Google.")
                
        with tab_ac:
            if not df_approv.empty and "stato" in df_approv.columns:
                pendenti = df_approv[df_approv["stato"] == "In attesa"]
                if mag_filtro_admin != "Tutti":
                    pendenti = pendenti[pendenti["magazzino"] == mag_filtro_admin]
                
                if pendenti.empty: 
                    st.info("Nessun ordine di rifornimento pendente per la selezione corrente.")
                for idx, row in pendenti.iterrows():
                    with st.container():
                        st.write(f"🏢 Reparto: **{row['magazzino']}** richiede {row['quantita_richiesta']}x **{row['articolo']}**")
                        if st.button("Approva ed Incrementa Stock", key=f"ap_ad_{row['id_acquisto']}"):
                            st.session_state.db_approvvigionamenti.loc[df_approv["id_acquisto"] == row["id_acquisto"], "stato"] = "Approvato"
                            
                            filtro = (df_inventario["nome_articolo"] == row["articolo"]) & (df_inventario["magazzino"] == row["magazzino"]) if not df_inventario.empty else pd.Series([False])
                            if filtro.any():
                                st.session_state.db_inventario.loc[filtro, "giacenza_totale"] += row["quantita_richiesta"]
                            else:
                                nuovo_p = pd.DataFrame([{"magazzino": row["magazzino"], "id_articolo": f"NEW_{row['id_acquisto']}", "nome_articolo": row["articolo"], "giacenza_totale": row["quantita_richiesta"]}])
                                st.session_state.db_inventario = pd.concat([st.session_state.db_inventario, nuovo_p], ignore_index=True)
                            
                            carica_su_sheet(st.session_state.db_inventario, "Inventario")
                            carica_su_sheet(st.session_state.db_approvvigionamenti, "Ordini")
                            st.rerun()
