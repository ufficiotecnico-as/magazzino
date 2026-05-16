import streamlit as st
import pandas as pd
from datetime import datetime

# ==========================================
# CONFIGURAZIONE PASSWORD / PIN DI ACCESSO
# ==========================================
PASSWORD_MAGAZZINIERE = "magazzino2026"
PASSWORD_ADMIN = "admin99"

st.set_page_config(page_title="Magazzino Online", page_icon="📦", layout="centered")

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
    st.title("🔑 Accesso Sistema Magazzino")
    scelta_accesso = st.radio("Chi sei?", ["Sono un Collaboratore (Richiesta materiale)", "Sono il Magazziniere / Admin"])
    
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

# --- INTERFACCE UTENTE ---
else:
    st.sidebar.write(f"Area: **{st.session_state.ruolo_utente.upper()}**")
    if st.sidebar.button("🔒 Esci / Cambia Utente"):
        st.session_state.ruolo_utente = None
        st.session_state.utente_corrente = ""
        st.rerun()
        
    # --- 1. AREA COLLABORATORE (Solo richieste) ---
    if st.session_state.ruolo_utente == "collaboratore":
        st.title(f"👋 Nuova Richiesta - {st.session_state.utente_corrente}")
        
        lista_articoli = st.session_state.db_inventario["nome_articolo"].tolist()
        articolo = st.selectbox("Seleziona l'articolo da richiedere:", lista_articoli)
        qta = st.number_input("Quantità necessaria:", min_value=1, step=1)
        
        if st.button("Invia Richiesta al Magazzino", use_container_width=True):
            nuovo_id = int(st.session_state.db_richieste["id_richiesta"].max()) + 1 if not st.session_state.db_richieste.empty else 1
            nuova_richiesta = pd.DataFrame([{
                "id_richiesta": nuovo_id,
                "collaboratore": st.session_state.utente_corrente,
                "articolo": articolo,
                "quantita": int(qta),
                "stato": "In attesa",
                "data_richiesta": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "data_consegna": ""
            }])
            st.session_state.db_richieste = pd.concat([st.session_state.db_richieste, nuova_richiesta], ignore_index=True)
            st.success("Richiesta inviata!")

    # --- 2. AREA MAGAZZINIERE (Consegne + Carico Giacenze iniziale/rifornimento) ---
    elif st.session_state.ruolo_utente == "magazziniere":
        st.title("🚚 Pannello Gestione Magazziniere")
        
        tab_consegne, tab_carico = st.tabs(["📋 Gestisci Richieste (Scarico)", "➕ Carica Nuove Giacenze / Inventario"])
        
        # SOTTO-PANNELLO 1: Gestioni consegne operative
        with tab_consegne:
            st.subheader("Richieste in attesa dai collaboratori")
            in_attesa = st.session_state.db_richieste[st.session_state.db_richieste["stato"] == "In attesa"]
            
            if in_attesa.empty:
                st.info("Nessuna richiesta pendente.")
            else:
                for idx, row in in_attesa.iterrows():
                    with st.container(border=True):
                        st.write(f"👤 **{row['collaboratore']}** richiede {row['quantita']}x **{row['articolo']}**")
                        if st.button("Consegna Materiale ✔", key=f"cons_{row['id_richiesta']}", use_container_width=True):
                            art = row['articolo']
                            qta_req = int(row['quantita'])
                            giacenza = int(st.session_state.db_inventario.loc[st.session_state.db_inventario["nome_articolo"] == art, "giacenza_totale"].values[0])
                            
                            if giacenza >= qta_req:
                                st.session_state.db_richieste.loc[st.session_state.db_richieste["id_richiesta"] == row["id_richiesta"], "stato"] = "Consegnato"
                                st.session_state.db_richieste.loc[st.session_state.db_richieste["id_richiesta"] == row["id_richiesta"], "data_consegna"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                                st.session_state.db_inventario.loc[st.session_state.db_inventario["nome_articolo"] == art, "giacenza_totale"] = giacenza - qta_req
                                st.success("Consegna registrata!")
                                st.rerun()
                            else:
                                st.error(f"Giacenza insufficiente! Disponibili in magazzino: {giacenza}")
                                
        # SOTTO-PANNELLO 2: Carico materiale (Funziona sia all'inizio che per i rifornimenti)
        with tab_carico:
            st.subheader("Aggiorna o Inserisci materiale in Giacenza")
            
            # 1. Modifica articoli esistenti
            st.write("🔧 **Aggiungi pezzi ad articoli esistenti:**")
            art_da_caricare = st.selectbox("Seleziona l'articolo da rifornire:", st.session_state.db_inventario["nome_articolo"].tolist())
            qta_da_aggiungere = st.number_input("Quantità da aggiungere al magazzino:", min_value=1, step=1, key="add_qta")
            
            if st.button("Esegui Carico Merce", use_container_width=True):
                giacenza_vecchia = int(st.session_state.db_inventario.loc[st.session_state.db_inventario["nome_articolo"] == art_da_caricare, "giacenza_totale"].values[0])
                st.session_state.db_inventario.loc[st.session_state.db_inventario["nome_articolo"] == art_da_caricare, "giacenza_totale"] = giacenza_vecchia + qta_da_aggiungere
                st.success(f"Giacenza aggiornata! Nuova giacenza per {art_da_caricare}: {giacenza_vecchia + qta_da_aggiungere} pezzi.")
                st.rerun()
                
            st.markdown("---")
            
            # 2. Creazione nuovo articolo (Se all'inizio l'elenco è vuoto o inserisci un nuovo tipo di prodotto)
            st.write("✨ **Inserisci un NUOVO articolo mai registrato prima:**")
            nuovo_id_art = st.text_input("Codice Articolo (es. A004):")
            nuovo_nome_art = st.text_input("Nome del nuovo materiale:")
            nuovo_stock_art = st.number_input("Giacenza iniziale inserita:", min_value=0, step=1)
            
            if st.button("Registra Nuovo Articolo nel Sistema"):
                if not nuovo_id_art.strip() or not nuevo_nome_art.strip():
                    st.error("Compila tutti i campi per creare l'articolo.")
                else:
                    nuovo_prodotto = pd.DataFrame([{"id_articolo": nuovo_id_art, "nome_articolo": nuovo_nome_art, "giacenza_totale": int(nuovo_stock_art)}])
                    st.session_state.db_inventario = pd.concat([st.session_state.db_inventario, nuovo_prodotto], ignore_index=True)
                    st.success(f"Articolo {nuovo_nome_art} inserito correttamente in inventario!")
                    st.rerun()

    # --- 3. AREA ADMIN (Report + Download Excel) ---
    elif st.session_state.ruolo_utente == "admin":
        st.title("📊 Pannello Amministratore (Admin)")
        
        st.subheader("📋 1. Stato Attuale delle Scorte (Inventario)")
        st.dataframe(st.session_state.db_inventario, use_container_width=True, hide_index=True)
        
        st.subheader("⏱ 2. Registro Storico Consegne")
        consegnati = st.session_state.db_richieste[st.session_state.db_richieste["stato"] == "Consegnato"]
        if consegnati.empty:
            st.info("Nessuna consegna nel registro.")
        else:
            st.dataframe(consegnati[["data_consegna", "collaboratore", "articolo", "quantita"]], use_container_width=True, hide_index=True)
            
        st.markdown("---")
        csv = st.session_state.db_richieste.to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 Scarica Registro Excel (CSV)", data=csv, file_name="registro_magazzino.csv", mime="text/csv", use_container_width=True)
