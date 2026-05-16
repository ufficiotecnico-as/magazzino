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

# Configurazione iniziale e mappatura corretta delle password
PASSWORD_MAP = {
    "ata2026": "Personale ATA",
    "officina2026": "Officina",
    "tecnici2026": "Tecnici Informatici"
}
PASSWORD_ADMIN = "admin99"

# Dizionario di mappatura basato sui reali nomi delle schede nel tuo Google Sheet
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

st.set_page_config(page_title="Gestione Magazzini Scarpa", page_icon="🧺", layout="wide")

# --- CONNESSIONE A GOOGLE SHEETS ---
@st.cache_resource(ttl=5)
def connetti_google_sheets():
    if not GSPREAD_AVAILABLE:
        st.error("Errore: La libreria `gspread` non è installata.")
        return None
    if "google_creds" not in st.secrets:
        st.error("Errore: Credenziali `google_creds` assenti nei Secrets di Streamlit.")
        return None
    try:
        creds_dict = dict(st.secrets["google_creds"])
        
        # Correzione dei caratteri di a capo nella chiave privata
        if "private_key" in creds_dict and "\\n" in creds_dict["private_key"]:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # Inizializzazione credenziali con supporto per l'universe domain
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
        
        # Gestione esplicita dell'universo dei domini di Google Cloud se presente nei Secrets
        if "universe_domain" in creds_dict:
            creds = creds.with_universe_domain(creds_dict["universe_domain"])
            
        return gspread.authorize(creds).open_by_key(SPREADSHEET_ID)
    except Exception as e:
        st.error(f"Errore critico di autenticazione: {e}")
        return None

# --- FUNZIONI DI LETTURA / SCRITTURA ---
def scarica_da_sheet(nome_scheda):
    sh = connetti_google_sheets()
    if sh is not None:
        try:
            worksheet = sh.worksheet(nome_scheda)
            records = worksheet.get_all_records()
            return pd.DataFrame(records)
        except gspread.exceptions.WorksheetNotFound:
            if "Inventario" in nome_scheda:
                df_base = pd.DataFrame(columns=["magazzino", "id_articolo", "nome_articolo", "giacenza_totale"])
            elif "Richieste" in nome_scheda:
                df_base = pd.DataFrame(columns=["id_richiesta", "magazzino", "collaboratore", "articolo", "quantita", "stato", "data_richiesta", "data_consegna"])
            else:
                df_base = pd.DataFrame(columns=["id_acquisto", "magazzino", "articolo", "quantita_richiesta", "stato", "data_richiesta"])
            carica_su_sheet(df_base, nome_scheda)
            return df_base
        except Exception as e:
            st.error(f"Errore di connessione a Google Sheets: {e}")
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
        except Exception as e:
            st.error(f"Errore salvataggio su scheda '{nome_scheda}': {e}")

# --- FUNZIONE DRIVE PER I DDT ---
def carica_su_drive(file_bytes, nome_file, mime_type, nome_magazzino):
    if not GOOGLE_DRIVE_AVAILABLE or "google_creds" not in st.secrets: 
        return None
    try:
        creds_dict = dict(st.secrets["google_creds"])
        if "private_key" in creds_dict and "\\n" in creds_dict["private_key"]:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            
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
    except Exception as e:
        st.error(f"Errore nell'invio del file a Drive: {e}")
        return None

# Inizializzazione variabili globali session_state
if "ruolo_utente" not in st.session_state: st.session_state.ruolo_utente = None
if "utente_corrente" not in st.session_state: st.session_state.utente_corrente = ""
if "magazzino_selezionato" not in st.session_state: st.session_state.magazzino_selezionato = None
if "scanned_code" not in st.session_state: st.session_state.scanned_code = ""

# --- STILE CUSTOM UX/UI ---
st.markdown("""
    <style>
        .stApp { background-color: #f1f5f9 !important; color: #0f172a !important; font-family: 'Inter', sans-serif; }
        [data-testid="stMainBlockContainer"] { max-width: 1150px; margin: 0 auto; padding-top: 2rem; }
        h1 { color: #0f172a !important; font-weight: 800 !important; text-align: center; margin-bottom: 30px !important; }
        h2, h3, h4, label, [data-testid="stWidgetLabel"] p { color: #1e293b !important; font-weight: 700 !important; }
        [data-testid="stContainer"] { background-color: #ffffff !important; border: 1px solid #e2e8f0 !important; border-radius: 16px !important; padding: 28px !important; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important; margin-bottom: 20px; }
        div.stButton > button:first-child { background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%) !important; color: #ffffff !important; border-radius: 10px !important; border: none !important; padding: 12px 24px !important; font-weight: 600 !important; width: 100%; }
        [data-testid="stSidebar"] { background-color: #ffffff !important; border-right: 1px solid #e2e8f0; }
        footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- INTERFACCIA LOGIN ---
if st.session_state.ruolo_utente is None:
    st.image(URL_LOGO, width="stretch")
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
                    else: 
                        st.error("❌ Password errata.")
else:
    st.image(URL_LOGO, width="stretch")

    with st.sidebar:
        st.markdown(f"<h3>🧺 Area {st.session_state.ruolo_utente.upper()}</h3>", unsafe_allow_html=True)
        if st.session_state.ruolo_utente == "magazziniere": 
            st.info(f"📍 Reparto: **{st.session_state.magazzino_selezionato}**")
        if st.button("🔒 Esci / Cambia Utente"):
            st.session_state.ruolo_utente = None
            st.session_state.scanned_code = ""
            st.rerun()

    # --- AREA COLLABORATORE ---
    if st.session_state.ruolo_utente == "collaboratore":
        st.markdown(f"<h1>👋 Benvenuto, {st.session_state.utente_corrente}</h1>", unsafe_allow_html=True)
        with st.container():
            target_magazzino = st.selectbox("A quale magazzino vuoi inviare la richiesta?", LISTA_MAGAZZINI)
            
            scheda_inv_nome = MAPPA_SCHEDE[target_magazzino]["inventario"]
            df_inventario_spec = scarica_da_sheet(scheda_inv_nome)
            
            articoli_filtrati = ["Altro..."]
            if not df_inventario_spec.empty and "nome_articolo" in df_inventario_spec.columns:
                lista_prodotti = df_inventario_spec["nome_articolo"].tolist()
                articoli_filtrati = lista_prodotti + ["Altro..."] if lista_prodotti else ["Altro..."]
                
            articolo_selezionato = st.selectbox("Seleziona cosa ti serve:", articoli_filtrati)
            articolo_finale = st.text_input("Specifica il materiale a mano:") if articolo_selezionato == "Altro..." else articolo_selezionato
            qta = st.number_input("Quantità necessaria:", min_value=1, step=1)
            
            if st.button("Invia Ordine in Magazzino"):
                scheda_rich_nome = MAPPA_SCHEDE[target_magazzino]["richieste"]
                df_richieste_spec = scarica_da_sheet(scheda_rich_nome)
                
                nuovo_id = int(df_richieste_spec["id_richiesta"].astype(float).max()) + 1 if not df_richieste_spec.empty else 1
                nuva_r = pd.DataFrame([{"id_richiesta": nuovo_id, "magazzino": target_magazzino, "collaboratore": st.session_state.utente_corrente, "articolo": articolo_finale, "quantita": int(qta), "stato": "In attesa", "data_richiesta": datetime.now().strftime("%d/%m/%Y %H:%M"), "data_consegna": ""}])
                
                df_richieste_spec = pd.concat([df_richieste_spec, nuva_r], ignore_index=True)
                carica_su_sheet(df_richieste_spec, scheda_rich_nome)
                st.success(f"✔️ Richiesta salvata nella scheda '{scheda_rich_nome}' di Google Fogli!")

    # --- AREA MAGAZZINIERE ---
    elif st.session_state.ruolo_utente == "magazziniere":
        mag_corrente = st.session_state.magazzino_selezionato
        st.markdown(f"<h1>🚚 Pannello Operativo: {mag_corrente}</h1>", unsafe_allow_html=True)
        
        scheda_inv_reale = MAPPA_SCHEDE[mag_corrente]["inventario"]
        scheda_rich_reale = MAPPA_SCHEDE[mag_corrente]["richieste"]
        
        df_inventario = scarica_da_sheet(scheda_inv_reale)
        df_richieste = scarica_da_sheet(scheda_rich_reale)
        df_approv = scarica_da_sheet("Ordini")
        
        tab_carico, tab_consegne, tab_rifornisci, tab_ddt = st.tabs(["📷 SCANNER REAL-TIME", "📋 Richieste dipendenti", "🛒 Ordini Nuovi", "📸 DDT"])
        
        with tab_carico:
            st.markdown("### 🎯 Carico tramite Fotocamera o Pistola USB")
            moltiplicatore_qta = st.number_input("Pezzi da aggiungere a ogni scansione:", min_value=1, value=1, step=1)
            
            foto_scattata = st.camera_input("Inquadra il codice a barre da vicino")
            if foto_scattata and PYZBAR_AVAILABLE:
                try:
                    img = Image.open(foto_scattata)
                    codici_rilevati = decode(img)
                    if codici_rilevati:
                        st.session_state.scanned_code = codici_rilevati[0].data.decode("utf-8").strip()
                    else:
                        st.error("❌ Codice non rilevato. Riprova con più luce.")
                except Exception as e:
                    st.error(f"Errore decodifica: {e}")

            manual_input = st.text_input("Lettore di Codici USB / Pistola Laser:")
            if manual_input.strip():
                st.session_state.scanned_code = manual_input.strip()

            if st.session_state.scanned_code:
                codice_pulito = str(st.session_state.scanned_code)
                st.markdown(f"📥 **Codice letto:** `{codice_pulito}`")
                
                filtro_art = (df_inventario["id_articolo"].astype(str) == codice_pulito) if not df_inventario.empty else pd.Series([False])
                
                if filtro_art.any():
                    df_inventario.loc[filtro_art, "giacenza_totale"] = df_inventario.loc[filtro_art, "giacenza_totale"].astype(int) + moltiplicatore_qta
                    carica_su_sheet(df_inventario, scheda_inv_reale)
                    st.success(f"✔️ Stock incrementato nella scheda '{scheda_inv_reale}'!")
                    if st.button("🔄 Nuova scansione"):
                        st.session_state.scanned_code = ""
                        st.rerun()
                else:
                    st.warning("🆕 Articolo non censito in questo reparto. Registralo adesso:")
                    with st.form("nuovo_prodotto_form"):
                        nome_nuovo = st.text_input("Nome del nuovo articolo:")
                        if st.form_submit_button("Salva nel database"):
                            if nome_nuovo.strip():
                                nuovo_p = pd.DataFrame([{"magazzino": mag_corrente, "id_articolo": codice_pulito, "nome_articolo": nome_nuovo.strip(), "giacenza_totale": int(moltiplicatore_qta)}])
                                df_inventario = pd.concat([df_inventario, nuovo_p], ignore_index=True)
                                carica_su_sheet(df_inventario, scheda_inv_reale)
                                st.success("✔️ Prodotto registrato online!")
                                st.session_state.scanned_code = ""
                                st.rerun()

            st.write("---")
            st.markdown(f"#### 📦 Inventario Attuale in '{scheda_inv_reale}'")
            if not df_inventario.empty:
                st.dataframe(df_inventario, use_container_width=True, hide_index=True)

        with tab_consegne:
            if not df_richieste.empty and "stato" in df_richieste.columns:
                richieste_mie = df_richieste[df_richieste["stato"] == "In attesa"]
                if richieste_mie.empty: 
                    st.info("Nessuna richiesta in attesa.")
                for idx, row in richieste_mie.iterrows():
                    with st.container():
                        st.write(f"👤 **{row['collaboratore']}** chiede {row['quantita']}x *{row['articolo']}*")
                        if st.button("Consegna Materiale ✔", key=f"ev_{row['id_richiesta']}"):
                            filtro = (df_inventario["nome_articolo"] == row['articolo'])
                            if filtro.any() and int(df_inventario.loc[filtro, "giacenza_totale"].values[0]) >= int(row['quantita']):
                                df_inventario.loc[filtro, "giacenza_totale"] = int(df_inventario.loc[filtro, "giacenza_totale"].values[0]) - int(row['quantita'])
                                df_richieste.loc[df_richieste["id_richiesta"].astype(str) == str(row["id_richiesta"]), "stato"] = "Consegnato"
                                df_richieste.loc[df_richieste["id_richiesta"].astype(str) == str(row["id_richiesta"]), "data_consegna"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                                
                                carica_su_sheet(df_inventario, scheda_inv_reale)
                                carica_su_sheet(df_richieste, scheda_rich_reale)
                                st.rerun()
                            else: 
                                st.error("❌ Stock insufficiente nel foglio Google!")

        with tab_rifornisci:
            mat_urgente = st.text_input("Articolo da ordinare:")
            qta_urgente = st.number_input("Q.tà:", min_value=1, step=1)
            if st.button("Invia Richiesta ad Admin"):
                nuovo_id_a = int(df_approv["id_acquisto"].astype(float).max()) + 1 if not df_approv.empty else 1
                nuovo_o = pd.DataFrame([{"id_acquisto": nuovo_id_a, "magazzino": mag_corrente, "articolo": mat_urgente, "quantita_richiesta": int(qta_urgente), "stato": "In attesa", "data_richiesta": datetime.now().strftime("%d/%m/%Y %H:%M")}])
                df_approv = pd.concat([df_approv, nuovo_o], ignore_index=True)
                carica_su_sheet(df_approv, "Ordini")
                st.success("✔️ Richiesta d'acquisto salvata nella scheda 'Ordini'!")

        with tab_ddt:
            file_ddt = st.file_uploader("Carica scansione DDT", type=["png", "jpg", "jpeg", "pdf"])
            fornitore = st.text_input("Fornitore:")
            if file_ddt and st.button("Invia ad Archivio Drive"):
                nome_f = f"DDT_{mag_corrente.replace(' ', '_')}_{fornitore}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                if carica_su_drive(file_ddt.getvalue(), nome_f, file_ddt.type, mag_corrente):
                    st.success("✔️ File caricato correttamente su Google Drive!")

    # --- AREA ADMIN ---
    elif st.session_state.ruolo_utente == "admin":
        st.markdown("<h1>👑 Pannello di Controllo Amministratore</h1>", unsafe_allow_html=True)
        mag_filtro_admin = st.selectbox("Seleziona Magazzino da analizzare:", LISTA_MAGAZZINI)
        
        tab_st, tab_ac = st.tabs(["📊 Giacenze Real-Time", "🛒 Approvazioni Rifornimenti"])
        
        with tab_st:
            scheda_inv_admin = MAPPA_SCHEDE[mag_filtro_admin]["inventario"]
            df_inventario_admin = scarica_da_sheet(scheda_inv_admin)
            st.markdown(f"### Scheda letta: `{scheda_inv_admin}`")
            if not df_inventario_admin.empty:
                st.dataframe(df_inventario_admin.sort_values(by="nome_articolo"), use_container_width=True, hide_index=True)
            else:
                st.info("Nessun dato o scheda vuota.")
                
        with tab_ac:
            df_approv_admin = scarica_da_sheet("Ordini")
            if not df_approv_admin.empty and "stato" in df_approv_admin.columns:
                pendenti = df_approv_admin[(df_approv_admin["stato"] == "In attesa") & (df_approv_admin["magazzino"] == mag_filtro_admin)]
                if pendenti.empty: 
                    st.info("Nessun ordine in attesa per questo reparto.")
                for idx, row in pendenti.iterrows():
                    with st.container():
                        st.write(f"🏢 **{row['magazzino']}** richiede {row['quantita_richiesta']}x **{row['articolo']}**")
                        if st.button("Approva ed Inserisci nello Stock", key=f"ap_ad_{row['id_acquisto']}"):
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
