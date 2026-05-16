import streamlit as st
import pandas as pd
from datetime import datetime
import json

st.set_page_config(page_title="Magazzino Cloud", page_icon="📦", layout="centered")
st.title("📦 Gestione Magazzino Online")

# Inizializzazione Database virtuale persistente tramite Streamlit Secrets
# Se non esistono dati nei secrets, creiamo una base dati iniziale pulita
if "db_inventario" not in st.session_state:
    try:
        # Carica i dati salvati nei secrets se presenti
        st.session_state.db_inventario = pd.DataFrame(json.loads(st.secrets["DATABASE_INVENTARIO"]))
        st.session_state.db_richieste = pd.DataFrame(json.loads(st.secrets["DATABASE_RICHIESTE"]))
    except:
        # Dati di backup pronti all'uso se i secrets sono vuoti alla prima configurazione
        st.session_state.db_inventario = pd.DataFrame([
            {"id_articolo": "A001", "nome_articolo": "Guanti da lavoro", "giacenza_totale": 100},
            {"id_articolo": "A002", "nome_articolo": "Scarpe antinfortunistiche", "giacenza_totale": 25},
            {"id_articolo": "A003", "nome_articolo": "Occhiali protettivi", "giacenza_totale": 50}
        ])
        st.session_state.db_richieste = pd.DataFrame(columns=["id_richiesta", "collaboratore", "articolo", "quantita", "stato", "data_richiesta", "data_consegna"])

df_inventario = st.session_state.db_inventario
df_richieste = st.session_state.db_richieste

# Menu di navigazione
ruolo = st.sidebar.radio("Vai a:", ["1. Richiesta Materiale (Collaboratore)", "2. Consegna (Magazziniere)", "3. Dashboard (Admin)"])

# --- 1. INTERFACCIA COLLABORATORE ---
if ruolo == "1. Richiesta Materiale (Collaboratore)":
    st.header("👋 Nuova Richiesta")
    nome = st.text_input("Inserisci il tuo Nome e Cognome:")
    
    lista_articoli = df_inventario["nome_articolo"].tolist()
    articolo = st.selectbox("Seleziona l'articolo da richiedere:", lista_articoli)
    qta = st.number_input("Quantità necessaria:", min_value=1, step=1)
    
    if st.button("Invia Richiesta", use_container_width=True):
        if not nome.strip():
            st.error("⚠️ Compila il campo Nome prima di inviare.")
        else:
            nuovo_id = int(df_richieste["id_richiesta"].max()) + 1 if not df_richieste.empty else 1
            
            nuova_richiesta = pd.DataFrame([{
                "id_richiesta": nuovo_id,
                "collaboratore": nome,
                "articolo": articolo,
                "quantita": int(qta),
                "stato": "In attesa",
                "data_richiesta": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "data_consegna": ""
            }])
            
            st.session_state.db_richieste = pd.concat([df_richieste, nuova_richiesta], ignore_index=True)
            st.success(f"Richiesta inviata con successo!")
            st.rerun()

# --- 2. INTERFACCIA MAGAZZINIERE ---
elif ruolo == "2. Consegna (Magazziniere)":
    st.header("🚚 Richieste in Attesa di Consegna")
    
    in_attesa = df_richieste[df_richieste["stato"] == "In attesa"]
    
    if in_attesa.empty:
        st.info("Ottimo lavoro! Non ci sono richieste pendenti.")
    else:
        for idx, row in in_attesa.iterrows():
            with st.container(border=True):
                st.write(f"👤 **{row['collaboratore']}**")
                st.write(f"📦 Materiale: {row['quantita']}x **{row['articolo']}**")
                
                if st.button("Marca come Consegnato ✔", key=f"consegna_{row['id_richiesta']}", use_container_width=True):
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
                        st.error(f"Errore: Giacenza insufficiente! Disponibili: {giacenza_attuale}")

# --- 3. INTERFACCIA ADMIN ---
elif ruolo == "3. Dashboard (Admin)":
    st.header("📊 Resoconto e Giacenze")
    
    st.subheader("📋 Inventario Attuale")
    st.dataframe(df_inventario, use_container_width=True, hide_index=True)
    
    st.subheader("⏱ Storico Consegne Effettuate")
    consegnati = df_richieste[df_richieste["stato"] == "Consegnato"]
    if consegnati.empty:
        st.info("Nessuna consegna registrata nello storico.")
    else:
        st.dataframe(consegnati[["data_consegna", "collaboratore", "articolo", "quantita"]], use_container_width=True, hide_index=True)
        
    # Bottone di emergenza per scaricare i dati in Excel/CSV in un clic
    st.markdown("---")
    csv = df_richieste.to_csv(index=False).encode('utf-8')
    st.download_button(label="📥 Scarica Registro Consegne (Excel / CSV)", data=csv, file_name="registro_consegne.csv", mime="text/csv", use_container_width=True)
