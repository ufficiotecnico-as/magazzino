import streamlit as st
import pandas as pd
from datetime import datetime

# ==========================================
# CONFIGURAZIONE PASSWORD / PIN DI ACCESSO
# Cambia queste scritte con le password che vuoi dare al personale
# ==========================================
PASSWORD_MAGAZZINIERE = "magazzino2026"
PASSWORD_ADMIN = "admin99"

st.set_page_config(page_title="Magazzino Privato", page_icon="📦", layout="centered")

# Inizializzazione del database virtuale nella memoria del server
if "db_inventario" not in st.session_state:
    st.session_state.db_inventario = pd.DataFrame([
        {"id_articolo": "A001", "nome_articolo": "Guanti da lavoro", "giacenza_totale": 100},
        {"id_articolo": "A002", "nome_articolo": "Scarpe antinfortunistiche", "giacenza_totale": 25},
        {"id_articolo": "A003", "nome_articolo": "Occhiali protettivi", "giacenza_totale": 50}
    ])

if "db_richieste" not in st.session_state:
    st.session_state.db_richieste = pd.DataFrame(columns=["id_richiesta", "collaboratore", "articolo", "quantita", "stato", "data_richiesta", "data_consegna"])

df_inventario = st.session_state.db_inventario
df_richieste = st.session_state.db_richieste

# Gestione dello stato di login dell'utente
if "ruolo_utente" not in st.session_state:
    st.session_state.ruolo_utente = None
if "utente_corrente" not in st.session_state:
    st.session_state.utente_corrente = ""

# --- SCHERMATA DI LOGIN INIZIALE ---
if st.session_state.ruolo_utente is None:
    st.title("🔑 Accesso Sistema Magazzino")
    st.write("Identificati per accedere alla tua area di lavoro.")
    
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
                st.error("❌ Password errata. Riprova.")

# --- SE SEI LOGGATO, MOSTRA L'INTERFACCIA CORRETTA ---
else:
    # Tasto di Logout sempre visibile in alto a destra nella barra laterale
    st.sidebar.write(f"Connesso come: **{st.session_state.ruolo_utente.upper()}**")
    if st.sidebar.button("🔒 Esci / Cambia Utente"):
        st.session_state.ruolo_utente = None
        st.session_state.utente_corrente = ""
        st.rerun()
        
    # --- 1. INTERFACCIA ESCLUSIVA COLLABORATORE ---
    if st.session_state.ruolo_utente == "collaboratore":
        st.title(f"👋 Area Richieste - {st.session_state.utente_corrente}")
        
        lista_articoli = df_inventario["nome_articolo"].tolist()
        articolo = st.selectbox("Seleziona l'articolo da richiedere:", lista_articoli)
        qta = st.number_input("Quantità necessaria:", min_value=1, step=1)
        
        if st.button("Invia Richiesta al Magazzino", use_container_width=True):
            nuovo_id = int(df_richieste["id_richiesta"].max()) + 1 if not df_richieste.empty else 1
            
            nuova_richiesta = pd.DataFrame([{
                "id_richiesta": nuovo_id,
                "collaboratore": st.session_state.utente_corrente,
                "articolo": articolo,
                "quantita": int(qta),
                "stato": "In attesa",
                "data_richiesta": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "data_consegna": ""
            }])
            
            st.session_state.db_richieste = pd.concat([df_richieste, nuova_richiesta], ignore_index=True)
            st.success(f"Richiesta inviata! Verrà esaminata dal magazziniere.")

    # --- 2. INTERFACCIA ESCLUSIVA MAGAZZINIERE ---
    elif st.session_state.ruolo_utente == "magazziniere":
        st.title("🚚 Pannello di Consegna (Magazziniere)")
        
        in_attesa = df_richieste[df_richieste["stato"] == "In attesa"]
        
        if in_attesa.empty:
            st.info("Nessuna richiesta in attesa di consegna al momento.")
        else:
            for idx, row in in_attesa.iterrows():
                with st.container(border=True):
                    st.write(f"👤 Collaboratore: **{row['collaboratore']}**")
                    st.write(f"📦 Materiale: {row['quantita']}x **{row['articolo']}**")
                    st.write(f"📅 Richiesto il: {row['data_richiesta']}")
                    
                    if st.button("Consegna e Aggiorna Scorte ✔", key=f"consegna_{row['id_richiesta']}", use_container_width=True):
                        art = row['articolo']
                        qta_richiesta = int(row['quantita'])
                        
                        giacenza_attuale = int(df_inventario.loc[df_inventario["nome_articolo"] == art, "giacenza_totale"].values[0])
                        
                        if giacenza_attuale >= qta_richiesta:
                            st.session_state.db_richieste.loc[st.session_state.db_richieste["id_richiesta"] == row["id_richiesta"], "stato"] = "Consegnato"
                            st.session_state.db_richieste.loc[st.session_state.db_richieste["id_richiesta"] == row["id_richiesta"], "data_consegna"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                            st.session_state.db_inventario.loc[st.session_state.db_inventario["nome_articolo"] == art, "giacenza_totale"] = giacenza_attuale - qta_richiesta
                            
                            st.success("Consegna registrata!")
                            st.rerun()
                        else:
                            st.error(f"Impossibile consegnare. Giacenza insufficiente (Disponibili: {giacenza_attuale})")

    # --- 3. INTERFACCIA ESCLUSIVA ADMIN ---
    elif st.session_state.ruolo_utente == "admin":
        st.title("📊 Pannello Amministratore (Admin)")
        
        st.subheader("📋 1. Giacenza di Magazzino Attuale")
        st.dataframe(df_inventario, use_container_width=True, hide_index=True)
        
        st.subheader("⏱ 2. Storico delle Consegne Effettuate")
        consegnati = df_richieste[df_richieste["stato"] == "Consegnato"]
        if consegnati.empty:
            st.info("Nessuna consegna presente nel registro storico.")
        else:
            st.dataframe(consegnati[["data_consegna", "collaboratore", "articolo", "quantita"]], use_container_width=True, hide_index=True)
            
        # Bottone di esportazione Excel/CSV automatica
        st.markdown("---")
        csv = df_richieste.to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 Scarica l'Excel Autocompilato del Registro", data=csv, file_name="registro_consegne.csv", mime="text/csv", use_container_width=True)
