import streamlit as st
import pandas as pd
from datetime import datetime

# ==========================================
# CONFIGURAZIONE PASSWORD / PIN DI ACCESSO
# ==========================================
PASSWORD_MAGAZZINIERE = "magazzino2026"
PASSWORD_ADMIN = "admin99"
URL_LOGO = "https://cspace.spaggiari.eu//pub/TVII0004/TVII0004-intestazione-nuova-senzaloghi.png?_t=1712923868"

# Configurazione della pagina con layout centrato e titolo nel browser
st.set_page_config(page_title="Gestione Magazzino Scarpa", page_icon="📦", layout="centered")

# --- ABBELLIMENTO INTERFACCIA TRAMITE CSS INIETTATO ---
st.markdown("""
    <style>
        /* Sfondo generale più morbido */
        .stApp {
            background-color: #f8f9fa;
        }
        /* Stile per i titoli */
        h1 {
            color: #1e3a8a !important;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-weight: 700;
            text-align: center;
            margin-bottom: 25px !important;
        }
        h2, h3 {
            color: #2563eb !important;
        }
        /* Personalizzazione dei bottoni principali */
        div.stButton > button:first-child {
            background-color: #2563eb;
            color: white;
            border-radius: 8px;
            border: none;
            padding: 10px 20px;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        div.stButton > button:first-child:hover {
            background-color: #1d4ed8;
            border: none;
            color: white;
            transform: translateY(-1px);
        }
        /* Card arrotondate per i moduli e le richieste */
        [data-testid="stContainer"] {
            background-color: white;
            border: 1px solid #e5e7eb !important;
            border-radius: 12px !important;
            padding: 20px !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important;
            margin-bottom: 15px;
        }
    </style>
""", unsafe_allow_html=True)

# Inizializzazione Database Persistente nella sessione dell'app
if "db_inventario" not in st.session_state:
    st.session_state.db_inventario = pd.DataFrame([
        {"id_articolo": "A001", "nome_articolo": "Guanti da lavoro", "giacenza_totale": 0},
        {"id_articolo": "A002", "nome_articolo": "Scarpe antinfortunistiche", "giacenza_totale": 0},
        {"id_articolo": "A003", "nome_articolo": "Occhiali protettivi", "giacenza_totale": 0}
    ])

if "db_richieste" not in st.session_state:
    st.session_state.db_richieste = pd.DataFrame(columns=["id_richiesta", "collaboratore", "articolo", "quantita", "stato", "data_richiesta", "data_consegna"])

# Gestione Login
if "ruolo_utente" not in st.session_state:
    st.session_state.ruolo_utente = None
if "utente_corrente" not in st.session_state:
    st.session_state.utente_corrente = ""

# --- SCHERMATA DI LOGIN ---
if st.session_state.ruolo_utente is None:
    # Inserimento del Logo aziendale centrato
    st.image(URL_LOGO, use_container_width=True)
    
    st.title("Gestione Magazzino Scarpa")
    
    # Card per il form di accesso
    with st.container():
        st.markdown("<h3 style='text-align: center; margin-top:0;'>🔑 Identificazione Utente</h3>", unsafe_allow_html=True)
        scelta_accesso = st.radio("Seleziona il tuo profilo:", ["Sono un Collaboratore (Richiesta materiale)", "Sono il Magazziniere / Admin"], label_visibility="collapsed")
        st.markdown("<br>", unsafe_allow_html=True)
        
        if scelta_accesso == "Sono un Collaboratore (Richiesta materiale)":
            nome_input = st.text_input("Inserisci il tuo Nome e Cognome:")
            if st.button("Accedi all'area Richieste", use_container_width=True):
                if not nome_input.strip():
                    st.error("⚠️ Inserisci il tuo nome per continuare.")
                else:
                    st.session_state.ruolo_utente = "collaboratore"
                    st.session_state.utente_corrente = nome_input.strip()
                    st.rerun()
                    
        elif scelta_accesso == "Sono il Magazziniere / Admin":
            password_input = st.text_input("Inserisci la password di sblocco:", type="password")
            if st.button("Verifica Password", use_container_width=True):
                if password_input == PASSWORD_MAGAZZINIERE:
                    st.session_state.ruolo_utente = "magazziniere"
                    st.rerun()
                elif password_input == PASSWORD_ADMIN:
                    st.session_state.ruolo_utente = "admin"
                    st.rerun()
                else:
                    st.error("❌ Password errata.")

# --- INTERFACCE UTENTE LOGGATO ---
else:
    # Mostra sempre il logo in alto anche nelle pagine interne per continuità grafica
    st.image(URL_LOGO, use_container_width=True)
    
    st.sidebar.markdown(f"<h3 style='text-align:center;'>📦 Area {st.session_state.ruolo_utente.upper()}</h3>", unsafe_allow_html=True)
    st.sidebar.markdown("---")
    if st.sidebar.button("🔒 Esci / Cambia Utente", use_container_width=True):
        st.session_state.ruolo_utente = None
        st.session_state.utente_corrente = ""
        st.rerun()
        
    # --- 1. AREA COLLABORATORE ---
    if st.session_state.ruolo_utente == "collaboratore":
        st.title(f"👋 Benvenuto, {st.session_state.utente_corrente}")
        
        with st.container():
            st.subheader("Compila la tua richiesta")
            lista_articoli = st.session_state.db_inventario["nome_articolo"].tolist()
            lista_articoli.append("Altro... (Materiale non in elenco o esaurito)")
            
            articolo_selezionato = st.selectbox("Seleziona l'articolo:", lista_articoli)
            
            if articolo_selezionato == "Altro... (Materiale non in elenco o esaurito)":
                articolo_finale = st.text_input("Specifica a mano il materiale richiesto:")
            else:
                articolo_finale = articolo_selezionato
                
            qta = st.number_input("Quantità necessaria:", min_value=1, step=1)
            st.markdown("<br>", unsafe_allow_html=True)
            
            if st.button("Invia Richiesta al Magazzino", use_container_width=True):
                if not articolo_finale.strip():
                    st.error("⚠️ Specifica il nome del materiale prima di inviare.")
                else:
                    nuovo_id = int(st.session_state.db_richieste["id_richiesta"].max()) + 1 if not st.session_state.db_richieste.empty else 1
                    nuova_richiesta = pd.DataFrame([{
                        "id_richiesta": nuovo_id,
                        "collaboratore": st.session_state.utente_corrente,
                        "articolo": articolo_finale.strip(),
                        "quantita": int(qta),
                        "stato": "In attesa",
                        "data_richiesta": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "data_consegna": ""
                    }])
                    st.session_state.db_richieste = pd.concat([st.session_state.db_richieste, nuova_richiesta], ignore_index=True)
                    st.success(f"Richiesta per '{articolo_finale}' inviata con successo!")

    # --- 2. AREA MAGAZZINIERE ---
    elif st.session_state.ruolo_utente == "magazziniere":
        st.title("🚚 Pannello Gestione Operativa")
        
        tab_consegne, tab_carico = st.tabs(["📋 Richieste da Consegnare (Scarico)", "➕ Registro e Carico Giacenze (Inventario)"])
        
        with tab_consegne:
            in_attesa = st.session_state.db_richieste[st.session_state.db_richieste["stato"] == "In attesa"]
            
            if in_attesa.empty:
                st.info("✨ Nessuna richiesta pendente. Tutto evaso!")
            else:
                for idx, row in in_attesa.iterrows():
                    with st.container():
                        st.markdown(f"**👤 Collaboratore:** {row['collaboratore']}")
                        st.markdown(f"**📦 Materiale:** {row['quantita']}x `<span style='color:#2563eb; font-weight:bold;'>{row['articolo']}</span>`", unsafe_allow_html=True)
                        st.markdown(f"**📅 Data richiesta:** {row['data_richiesta']}")
                        
                        if st.button("Marca come Consegnato ✔", key=f"cons_{row['id_richiesta']}", use_container_width=True):
                            art = row['articolo']
                            qta_req = int(row['quantita'])
                            
                            filtro_art = st.session_state.db_inventario["nome_articolo"] == art
                            if filtro_art.any():
                                giacenza = int(st.session_state.db_inventario.loc[filtro_art, "giacenza_totale"].values[0])
                                
                                if giacenza >= qta_req:
                                    st.session_state.db_richieste.loc[st.session_state.db_richieste["id_richiesta"] == row["id_richiesta"], "stato"] = "Consegnato"
                                    st.session_state.db_richieste.loc[st.session_state.db_richieste["id_richiesta"] == row["id_richiesta"], "data_consegna"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                                    st.session_state.db_inventario.loc[filtro_art, "giacenza_totale"] = giacenza - qta_req
                                    st.success("Consegna registrata con successo!")
                                    st.rerun()
                                else:
                                    st.error(f"Giacenza insufficiente! Disponibili: {giacenza}")
                            else:
                                st.error(f"⚠️ L'articolo '{art}' è stato inserito come 'Altro'. Registralo nella scheda a fianco prima di effettuare la consegna.")
                                
        with tab_carico:
            with st.container():
                st.markdown("### 🔧 Aggiungi pezzi a materiale esistente")
                art_da_caricare = st.selectbox("Seleziona l'articolo:", st.session_state.db_inventario["nome_articolo"].tolist())
                qta_da_aggiungere = st.number_input("Quantità arrivata:", min_value=1, step=1, key="add_qta")
                
                if st.button("Esegui Carico Merce", use_container_width=True):
                    giacenza_vecchia = int(st.session_state.db_inventario.loc[st.session_state.db_inventario["nome_articolo"] == art_da_caricare, "giacenza_totale"].values[0])
                    st.session_state.db_inventario.loc[st.session_state.db_inventario["nome_articolo"] == art_da_caricare, "giacenza_totale"] = giacenza_vecchia + qta_da_aggiungere
                    st.success(f"Giacenza aggiornata! Totale attuale per {art_da_caricare}: {giacenza_vecchia + qta_da_aggiungere} pezzi.")
                    st.rerun()
                    
            with st.container():
                st.markdown("### ✨ Registra un NUOVO articolo mai inserito")
                nuovo_id_art = st.text_input("Codice Identificativo (es. A004):")
                nuovo_nome_art = st.text_input("Nome del materiale:")
                nuovo_stock_art = st.number_input("Stock iniziale inserito:", min_value=0, step=1)
                
                if st.button("Salva Nuovo Articolo nel Registro", use_container_width=True):
                    if not nuovo_id_art.strip() or not nuovo_nome_art.strip():
                        st.error("Compila tutti i campi per creare l'articolo.")
                    else:
                        nuovo_prodotto = pd.DataFrame([{"id_articolo": nuovo_id_art, "nome_articolo": nuovo_nome_art, "giacenza_totale": int(nuovo_stock_art)}])
                        st.session_state.db_inventario = pd.concat([st.session_state.db_inventario, nuovo_prodotto], ignore_index=True)
                        st.success(f"Articolo '{nuovo_nome_art}' inserito correttamente!")
                        st.rerun()

    # --- 3. AREA ADMIN ---
    elif st.session_state.ruolo_utente == "admin":
        st.title("📊 Controllo Amministratore (Admin)")
        
        st.subheader("📋 Giacenza di Magazzino Attuale")
        st.dataframe(st.session_state.db_inventario, use_container_width=True, hide_index=True)
        
        st.subheader("⏱ Registro Storico Consegne")
        consegnati = st.session_state.db_richieste[st.session_state.db_richieste["stato"] == "Consegnato"]
        if consegnati.empty:
            st.info("Nessuna consegna presente nel registro storico.")
        else:
            st.dataframe(consegnati[["data_consegna", "collaboratore", "articolo", "quantita"]], use_container_width=True, hide_index=True)
            
        st.markdown("<br>", unsafe_allow_html=True)
        csv = st.session_state.db_richieste.to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 Scarica Report Excel / CSV Completo", data=csv, file_name="registro_magazzino_scarpa.csv", mime="text/csv", use_container_width=True)
