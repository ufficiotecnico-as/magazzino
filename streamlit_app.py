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

# --- CONNESSIONE A GOOGLE SHEETS ---
@st.cache_resource(ttl=2)
def connetti_google_sheets():
    if not GSPREAD_AVAILABLE:
        st.error("Errore: La libreria `gspread` non è installata.")
        return None
    if "google_creds" not in st.secrets:
        st.error("Errore: Configurazione [google_creds] mancante nei Secrets.")
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
    except Exception as e:
        st.error(f"Errore di autenticazione Google: {str(e)}")
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
        except Exception as e:
            st.error(f"Errore lettura '{nome_scheda}': {e}")
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
            st.error(f"Errore salvataggio '{nome_scheda}': {e}")

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
    except Exception as e:
        st.error(f"Errore nell'invio del file a Drive: {e}")
        return None

# Stato sessione iniziale
if "ruolo_utente" not in st.session_state: st.session_state.ruolo_utente = None
if "utente_corrente" not in st.session_state: st.session_state.utente_corrente = ""
if "magazzino_selezionato" not in st.session_state: st.session_state.magazzino_selezionato = None
if "scanned_code" not in st.session_state: st.session_state.scanned_code = ""

# --- LOG INTERFACCIA DI ACCESSO ---
if st.session_state.ruolo_utente is None:
    st.image(URL_LOGO, use_container_width=True)
    st.markdown("<br><h2 style='text-align: center; color: #1e293b; font-weight: 700;'>Piattaforma Logistica di Istituto</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #64748b; margin-bottom: 40px;'>Seleziona la modalità d'ingresso per accedere ai servizi di inventario</p>", unsafe_allow_html=True)
    
    col_l, col_c, col_r = st.columns([1, 1.8, 1])
    with col_c:
        with st.card():
            scelta_accesso = st.segmented_control(
                "Tipo Accesso",
                options=["Collaboratore", "Staff Magazzino / Admin"],
                default="Collaboratore",
                label_visibility="collapsed"
            )
            
            st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
            
            if scelta_accesso == "Collaboratore":
                nome_input = st.text_input("Nome e Cognome del Richiedente", placeholder="es. Mario Rossi")
                if st.button("Accedi al modulo richieste", use_container_width=True, type="primary"):
                    if nome_input.strip():
                        st.session_state.ruolo_utente = "collaboratore"
                        st.session_state.utente_corrente = nome_input.strip()
                        st.rerun()
                    else:
                        st.warning("Inserisci un nome valido per continuare.")
            else:
                password_input = st.text_input("Chiave di autenticazione", type="password", placeholder="••••••••")
                if st.button("Verifica credenziali", use_container_width=True, type="primary"):
                    if password_input in PASSWORD_MAP:
                        st.session_state.ruolo_utente = "magazziniere"
                        st.session_state.magazzino_selezionato = PASSWORD_MAP[password_input]
                        st.rerun()
                    elif password_input == PASSWORD_ADMIN:
                        st.session_state.ruolo_utente = "admin"
                        st.rerun()
                    else: 
                        st.error("Chiave di sicurezza non valida.")
else:
    # --- HEADER APPLICAZIONE AVVIATA ---
    st.image(URL_LOGO, use_container_width=True)
    
    # Barra di stato utente superiore elegante
    col_info, col_logout = st.columns([4, 1])
    with col_info:
        if st.session_state.ruolo_utente == "collaboratore":
            st.markdown(f"👤 Area Personale: **{st.session_state.utente_corrente}** | Ruolo: *Richiedente materiale*")
        elif st.session_state.ruolo_utente == "magazziniere":
            st.markdown(f"📦 Terminale Attivo: **{st.session_state.magazzino_selezionato}** | Ruolo: *Operatore logistico*")
        else:
            st.markdown(f"👑 Console Principale | Ruolo: *Amministratore di Sistema*")
    with col_logout:
        if st.button("Disconnetti", use_container_width=True, type="secondary"):
            st.session_state.ruolo_utente = None
            st.session_state.scanned_code = ""
            st.rerun()
            
    st.markdown("<hr style='margin: 10px 0 25px 0; border-color: #e2e8f0;'>", unsafe_allow_html=True)

    # --- 1. AREA COLLABORATORE ---
    if st.session_state.ruolo_utente == "collaboratore":
        st.markdown("<h3 style='color: #0f172a;'>Nuova richiesta di prelievo materiale</h3>", unsafe_allow_html=True)
        
        with st.card():
            col1, col2 = st.columns(2)
            with col1:
                target_magazzino = st.selectbox("Magazzino di riferimento", LISTA_MAGAZZINI)
            
            scheda_inv_nome = MAPPA_SCHEDE[target_magazzino]["inventario"]
            df_inventario_spec = scarica_da_sheet(scheda_inv_nome)
            
            articoli_filtrati = ["Altro (Inserimento manuale)"]
            if not df_inventario_spec.empty and "nome_articolo" in df_inventario_spec.columns:
                articoli_filtrati = df_inventario_spec["nome_articolo"].tolist() + ["Altro (Inserimento manuale)"]
                
            with col2:
                articolo_selezionato = st.selectbox("Articolo richiesto", articoli_filtrati)
            
            if articolo_selezionato == "Altro (Inserimento manuale)":
                articolo_finale = st.text_input("Specifica il nome dell'articolo:")
            else:
                articolo_finale = articolo_selezionato
                
            qta = st.number_input("Quantità desiderata", min_value=1, step=1, value=1)
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Invia ordine al magazzino selezionato", type="primary"):
                if articolo_finale:
                    scheda_rich_nome = MAPPA_SCHEDE[target_magazzino]["richieste"]
                    df_richieste_spec = scarica_da_sheet(scheda_rich_nome)
                    
                    nuovo_id = int(df_richieste_spec["id_richiesta"].astype(float).max()) + 1 if not df_richieste_spec.empty else 1
                    nuva_r = pd.DataFrame([{"id_richiesta": nuovo_id, "magazzino": target_magazzino, "collaboratore": st.session_state.utente_corrente, "articolo": articolo_finale, "quantita": int(qta), "stato": "In attesa", "data_richiesta": datetime.now().strftime("%d/%m/%Y %H:%M"), "data_consegna": ""}])
                    
                    df_richieste_spec = pd.concat([df_richieste_spec, nuva_r], ignore_index=True)
                    carica_su_sheet(df_richieste_spec, scheda_rich_nome)
                    st.success("✔️ Richiesta inoltrata correttamente. Il magazziniere prenderà in carico l'ordine.")
                else:
                    st.error("Per favore, specifica l'articolo.")

    # --- 2. AREA MAGAZZINIERE ---
    elif st.session_state.ruolo_utente == "magazziniere":
        mag_corrente = st.session_state.magazzino_selezionato
        
        scheda_inv_reale = MAPPA_SCHEDE[mag_corrente]["inventario"]
        scheda_rich_reale = MAPPA_SCHEDE[mag_corrente]["richieste"]
        
        df_inventario = scarica_da_sheet(scheda_inv_reale)
        df_richieste = scarica_da_sheet(scheda_rich_reale)
        df_approv = scarica_da_sheet("Ordini")
        
        tab_carico, tab_consegne, tab_rifornisci, tab_ddt = st.tabs([
            "📷 SCANNER CODICI", 
            "📋 RICHIESTE DIPENDENTI", 
            "🛒 RIFORNIMENTI", 
            "📸 ARCHIVIAZIONE DDT"
        ])
        
        with tab_carico:
            col_scan, col_manual = st.columns([1.5, 1])
            
            with col_scan:
                with st.card():
                    st.markdown("##### 📷 Lettura Codice a Barre")
                    moltiplicatore_qta = st.number_input("Pezzi da caricare ad ogni lettura:", min_value=1, value=1)
                    
                    foto_scattata = st.camera_input("Inquadra il barcode")
                    if foto_scattata and PYZBAR_AVAILABLE:
                        try:
                            codici_rilevati = decode(Image.open(foto_scattata))
                            if codici_rilevati:
                                st.session_state.scanned_code = codici_rilevati[0].data.decode("utf-8").strip()
                            else:
                                st.toast("Nessun codice rilevato nella foto.", icon="⚠️")
                        except Exception as e:
                            st.error(f"Errore di decodifica ottica: {e}")
            
            with col_manual:
                with st.card():
                    st.markdown("##### ⌨️ Input Manuale o Pistola Laser USB")
                    manual_input = st.text_input("Incolla codice o spara con la pistola:", placeholder="Codice articolo...")
                    if manual_input.strip():
                        st.session_state.scanned_code = manual_input.strip()

            if st.session_state.scanned_code:
                codice_pulito = str(st.session_state.scanned_code)
                st.markdown(f"<div style='background-color: #f0fdf4; padding: 15px; border-radius: 10px; border: 1px solid #bbf7d0; margin: 15px 0;'>📦 <b>Codice Attivo Rilevato:</b> <code>{codice_pulito}</code></div>", unsafe_allow_html=True)
                
                filtro_art = (df_inventario["id_articolo"].astype(str) == codice_pulito) if not df_inventario.empty else pd.Series([False])
                
                if filtro_art.any():
                    if st.button(f"Conferma Carico (+ {moltiplicatore_qta} unità)", type="primary", use_container_width=True):
                        df_inventario.loc[filtro_art, "giacenza_totale"] = df_inventario.loc[filtro_art, "giacenza_totale"].astype(int) + moltiplicatore_qta
                        carica_su_sheet(df_inventario, scheda_inv_reale)
                        st.success("Stock aggiornato con successo!")
                        st.session_state.scanned_code = ""
                        st.rerun()
                else:
                    st.warning("L'articolo non è presente nell'inventario di questo reparto. Registralo ora:")
                    with st.form("nuovo_prodotto_form"):
                        nome_nuovo = st.text_input("Assegna un nome all'articolo:")
                        if st.form_submit_button("Salva ed inserisci a catalogo", use_container_width=True):
                            if nome_nuovo.strip():
                                nuovo_p = pd.DataFrame([{"magazzino": mag_corrente, "id_articolo": codice_pulito, "nome_articolo": nome_nuovo.strip(), "giacenza_totale": int(moltiplicatore_qta)}])
                                df_inventario = pd.concat([df_inventario, nuovo_p], ignore_index=True)
                                carica_su_sheet(df_inventario, scheda_inv_reale)
                                st.success("Nuovo codice registrato nel database!")
                                st.session_state.scanned_code = ""
                                st.rerun()

            st.markdown("<br><h5>📦 Giacenze di Reparto in Tempo Reale</h5>", unsafe_allow_html=True)
            if not df_inventario.empty:
                st.dataframe(df_inventario, use_container_width=True, hide_index=True)
            else:
                st.info("L'inventario è attualmente vuoto.")

        with tab_consegne:
            st.markdown("##### 📋 Elenco materiali richiesti dal personale")
            if not df_richieste.empty and "stato" in df_richieste.columns:
                richieste_mie = df_richieste[df_richieste["stato"] == "In attesa"]
                if richieste_mie.empty: 
                    st.info("Ottimo lavoro! Non ci sono richieste pendenti da evadere.")
                else:
                    for idx, row in richieste_mie.iterrows():
                        with st.card():
                            col_testo, col_azione = st.columns([3, 1])
                            with col_testo:
                                st.markdown(f"👤 **{row['collaboratore']}** richiede **{row['quantita']}** pz. di ` {row['articolo']} `")
                                st.caption(f"Richiesto il: {row['data_richiesta']}")
                            with col_azione:
                                if st.button("Evadi e Consegna ✔", key=f"ev_{row['id_richiesta']}", use_container_width=True, type="primary"):
                                    filtro = (df_inventario["nome_articolo"] == row['articolo'])
                                    if filtro.any() and int(df_inventario.loc[filtro, "giacenza_totale"].values[0]) >= int(row['quantita']):
                                        df_inventario.loc[filtro, "giacenza_totale"] = int(df_inventario.loc[filtro, "giacenza_totale"].values[0]) - int(row['quantita'])
                                        df_richieste.loc[df_richieste["id_richiesta"].astype(str) == str(row["id_richiesta"]), "stato"] = "Consegnato"
                                        df_richieste.loc[df_richieste["id_richiesta"].astype(str) == str(row["id_richiesta"]), "data_consegna"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                                        
                                        carica_su_sheet(df_inventario, scheda_inv_reale)
                                        carica_su_sheet(df_richieste, scheda_rich_reale)
                                        st.rerun()
                                    else: 
                                        st.error("Scorte insufficienti nel foglio per completare il prelievo.")

        with tab_rifornisci:
            st.markdown("##### 🛒 Segnala materiale esaurito all'Amministrazione")
            with st.card():
                mat_urgente = st.text_input("Descrizione articolo o bene:")
                qta_urgente = st.number_input("Quantità pacchi/unità:", min_value=1, step=1, value=1)
                if st.button("Invia richiesta di approvvigionamento", type="primary", use_container_width=True):
                    if mat_urgente.strip():
                        nuovo_id_a = int(df_approv["id_acquisto"].astype(float).max()) + 1 if not df_approv.empty else 1
                        nuovo_o = pd.DataFrame([{"id_acquisto": nuovo_id_a, "magazzino": mag_corrente, "articolo": mat_urgente.strip(), "quantita_richiesta": int(qta_urgente), "stato": "In attesa", "data_richiesta": datetime.now().strftime("%d/%m/%Y %H:%M")}])
                        df_approv = pd.concat([df_approv, nuovo_o], ignore_index=True)
                        carica_su_sheet(df_approv, "Ordini")
                        st.success("Richiesta d'acquisto salvata e inoltrata alla dashboard Admin.")
                    else:
                        st.error("Inserisci il nome del materiale.")

        with tab_ddt:
            st.markdown("##### 📸 Archiviazione Digitale Documenti di Trasporto")
            with st.card():
                file_ddt = st.file_uploader("Seleziona o fotografa il documento fiscale (DDT)", type=["png", "jpg", "jpeg", "pdf"])
                fornitore = st.text_input("Azienda / Fornitore:")
                if file_ddt and st.button("Carica su Cloud Drive", type="primary", use_container_width=True):
                    if fornitore.strip():
                        nome_f = f"DDT_{mag_corrente.replace(' ', '_')}_{fornitore.strip()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                        if carica_su_drive(file_ddt.getvalue(), nome_f, file_ddt.type, mag_corrente):
                            st.success("DDT catalogato e archiviato nella cartella Google Drive corretta.")
                    else:
                        st.error("Specifica il nome del fornitore.")

    # --- 3. AREA ADMIN ---
    elif st.session_state.ruolo_utente == "admin":
        st.markdown("<h3 style='color: #0f172a;'>Consolle Centrale di Controllo</h3>", unsafe_allow_html=True)
        
        mag_filtro_admin = st.selectbox("Seleziona Magazzino da esaminare:", LISTA_MAGAZZINI)
        
        tab_st, tab_ac = st.tabs(["📊 SCORTE DISPONIBILI", "⚖️ APPROVAZIONE ACQUISTI"])
        
        with tab_st:
            scheda_inv_admin = MAPPA_SCHEDE[mag_filtro_admin]["inventario"]
            df_inventario_admin = scarica_da_sheet(scheda_inv_admin)
            st.markdown(f"Stato attuale del database per: **{scheda_inv_admin}**")
            if not df_inventario_admin.empty:
                st.dataframe(df_inventario_admin.sort_values(by="nome_articolo"), use_container_width=True, hide_index=True)
            else:
                st.info("Nessun articolo registrato in questa sezione.")
                
        with tab_ac:
            df_approv_admin = scarica_da_sheet("Ordini")
            if not df_approv_admin.empty and "stato" in df_approv_admin.columns:
                pendenti = df_approv_admin[(df_approv_admin["stato"] == "In attesa") & (df_approv_admin["magazzino"] == mag_filtro_admin)]
                if pendenti.empty: 
                    st.info("Non ci sono nuove richieste di acquisto per questo magazzino.")
                else:
                    for idx, row in pendenti.iterrows():
                        with st.card():
                            c_t, c_b = st.columns([3, 1])
                            with c_t:
                                st.markdown(f"🏢 Il reparto **{row['magazzino']}** necessita di:")
                                st.markdown(f"#### {row['quantita_richiesta']}x {row['articolo']}")
                                st.caption(f"Richiesta registrata il: {row['data_richiesta']}")
                            with c_b:
                                if st.button("Autorizza e Inserisci", key=f"ap_ad_{row['id_acquisto']}", use_container_width=True, type="primary"):
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
