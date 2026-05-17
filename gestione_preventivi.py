import streamlit as st
import pandas as pd
from datetime import datetime

def mostra_interfaccia_preventivi(scarica_da_sheet, carica_su_sheet, invia_email_sistema, url_intermediario, df_istanze):
    st.markdown("## 📊 Hub Ufficio Tecnico: Gestione Preventivi e Fornitori")
    st.markdown("Qui puoi gestire le richieste nate dai vari magazzini e associarvi i preventivi ricevuti dai fornitori.")
    
    # Caricamento dei dati
    df_richieste_mag = scarica_da_sheet("Richieste_Preventivo_Magazzino")
    df_preventivi = scarica_da_sheet("Registro_Preventivi")
    df_fornitori = scarica_da_sheet("Anagrafica_Fornitori")
    
    # Inizializzazione se vuoti
    if df_richieste_mag.empty:
        st.info("📦 Nessuna richiesta inserita dai magazzini al momento.")
        return
    if df_preventivi.empty:
        df_preventivi = pd.DataFrame(columns=["id_preventivo", "id_richiesta_mag", "fornitore", "importo_ivato", "data_inserimento", "stato_approvazione", "note"])
    if df_fornitori.empty:
        df_fornitori = pd.DataFrame([{"id_fornitore": "F01", "ragione_sociale": "Forniture Rossi Srl", "partita_iva": "01234567890", "email_contatto": "info@rossi.it"}])
        carica_su_sheet(df_fornitori, "Anagrafica_Fornitori")

    tab_elabora, tab_registro, tab_fornitori = st.tabs([
        "✍️ 1. Assegna Preventivo a Richiesta Magazzino",
        "📜 2. Registro Generale Acquisti",
        "🏢 3. Anagrafica Fornitori"
    ])

    # TAB 1: L'UFFICIO TECNICO ASSOCIA IL PREVENTIVO ALLA RICHIESTA DEL MAGAZZINO
    with tab_elabora:
        richieste_attive = df_richieste_mag[df_richieste_mag["stato_iter"] == "In attesa di preventivi"]
        
        if richieste_attive.empty:
            st.success("✅ Tutte le richieste del magazzino hanno già un preventivo associato!")
        else:
            opzioni_rm = [f"REQ {r['id_richiesta_mag']} dal magazzino {r['magazzino_origine']}: {r['materiale_richiesto']}" for _, r in richieste_attive.iterrows()]
            scelta = st.selectbox("Seleziona la richiesta del magazzino da girare al fornitore:", opzioni_rm)
            id_rm_scelto = scelta.split(" ")[1]
            
            lista_f = df_fornitori["ragione_sociale"].tolist()
            fornitore_scelto = st.selectbox("Seleziona il Fornitore a cui hai chiesto il preventivo:", lista_f)
            
            with st.form("form_ufficio_tecnico"):
                col1, col2 = st.columns(2)
                with col1:
                    importo = st.number_input("Importo del Preventivo (€, IVA inclusa):", min_value=0.0, step=10.0)
                with col2:
                    note_p = st.text_input("Note / Riferimento Offerta:")
                
                if st.form_submit_button("Registra e Collega Preventivo"):
                    if importo > 0:
                        id_p = 7001 if df_preventivi.empty else int(pd.to_numeric(df_preventivi["id_preventivo"], errors='coerce').max()) + 1
                        
                        nuovo_prev = pd.DataFrame([{
                            "id_preventivo": id_p, "id_richiesta_mag": id_rm_scelto, "fornitore": fornitore_scelto,
                            "importo_ivato": f"{importo:.2f}", "data_inserimento": datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "stato_approvazione": "In attesa di validazione DSGA/DS", "note": note_p.strip()
                        }])
                        
                        # Aggiorna lo stato della richiesta del magazziniere
                        df_richieste_mag.loc[df_richieste_mag["id_richiesta_mag"].astype(str) == str(id_rm_scelto), "stato_iter"] = "Preventivo Caricato dall'Ufficio Tecnico"
                        
                        carica_su_sheet(pd.concat([df_preventivi, nuovo_prev], ignore_index=True), "Registro_Preventivi")
                        carica_su_sheet(df_richieste_mag, "Richieste_Preventivo_Magazzino")
                        st.success(f"💥 Preventivo {id_p} associato alla richiesta {id_rm_scelto}!")
                        st.rerun()

    # TAB 2: VISTA GENERALE
    with tab_registro:
        st.markdown("#### Richieste dei Magazzini")
        st.dataframe(df_richieste_mag, use_container_width=True, hide_index=True)
        st.markdown("#### Preventivi Associati")
        st.dataframe(df_preventivi, use_container_width=True, hide_index=True)

    # TAB 3: FORNITORI
    with tab_fornitori:
        st.dataframe(df_fornitori, use_container_width=True, hide_index=True)
