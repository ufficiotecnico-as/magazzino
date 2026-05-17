import streamlit as st
import pandas as pd
from datetime import datetime

def mostra_interfaccia_preventivi(scarica_da_sheet, carica_su_sheet, invia_email_sistema, url_intermediario, df_istanze):
    st.markdown("## 📊 Hub Ufficio Tecnico: Assegnazione Preventivi a Fabbisogni Magazzino")
    
    df_richieste_mag = scarica_da_sheet("Richieste_Preventivo_Magazzino")
    df_preventivi = scarica_da_sheet("Registro_Preventivi")
    df_fornitori = scarica_da_sheet("Anagrafica_Fornitori")
    
    if df_richieste_mag.empty:
        st.info("📦 Nessuna richiesta di acquisto inoltrata dai magazzini al momento.")
        return
        
    if df_preventivi.empty:
        df_preventivi = pd.DataFrame(columns=["id_preventivo", "id_richiesta_mag", "fornitore", "importo_ivato", "data_inserimento", "stato_approvazione", "note"])
    if df_fornitori.empty:
        df_fornitori = pd.DataFrame([{"id_fornitore": "F01", "ragione_sociale": "Forniture Rossi Srl", "partita_iva": "01234567890", "email_contatto": "info@rossi.it"}])
        carica_su_sheet(df_fornitori, "Anagrafica_Fornitori")

    richieste_attive = df_richieste_mag[df_richieste_mag["stato_iter"] == "In attesa di preventivi"]
    
    if richieste_attive.empty:
        st.success("✅ Tutte le richieste del magazzino sono state evase o hanno un preventivo associato.")
    else:
        opzioni_rm = [f"REQ {r['id_richiesta_mag']} [{r['magazzino_origine']}]: {r['materiale_richiesto']}" for _, r in richieste_attive.iterrows()]
        scelta = st.selectbox("Seleziona il fabbisogno del magazzino da girare al fornitore:", opzioni_rm)
        id_rm_scelto = scelta.split(" ")[1]
        
        fornitore_scelto = st.selectbox("Ditta Fornitrice:", df_fornitori["ragione_sociale"].tolist())
        
        with st.form("form_salva_prev"):
            importo = st.number_input("Costo Preventivato (€, IVA Inclusa):", min_value=0.0)
            note_p = st.text_input("Riferimento preventivo / Note:")
            if st.form_submit_button("Collega ed Invia Preventivo a Registro"):
                if importo > 0:
                    id_p = 7001 if df_preventivi.empty else int(pd.to_numeric(df_preventivi["id_preventivo"], errors='coerce').max()) + 1
                    nuovo = pd.DataFrame([{"id_preventivo": id_p, "id_richiesta_mag": id_rm_scelto, "fornitore": fornitore_scelto, "importo_ivato": f"{importo:.2f}", "data_inserimento": datetime.now().strftime("%d/%m/%Y %H:%M"), "stato_approvazione": "In attesa di validazione Dirigente", "note": note_p.strip()}])
                    df_richieste_mag.loc[df_richieste_mag["id_richiesta_mag"].astype(str) == str(id_rm_scelto), "stato_iter"] = "Preventivo Ricevuto"
                    carica_su_sheet(pd.concat([df_preventivi, nuovo], ignore_index=True), "Registro_Preventivi")
                    carica_su_sheet(df_richieste_mag, "Richieste_Preventivo_Magazzino")
                    st.success("Preventivo agganciato con successo!")
                    st.rerun()

    st.markdown("### 📜 Riepilogo Richieste Interne Magazzini")
    st.dataframe(df_richieste_mag, use_container_width=True, hide_index=True)import streamlit as st
import pandas as pd
from datetime import datetime

def mostra_interfaccia_preventivi(scarica_da_sheet, carica_su_sheet, invia_email_sistema, url_intermediario, df_istanze):
    st.markdown("## 📊 Hub Ufficio Tecnico: Assegnazione Preventivi a Fabbisogni Magazzino")
    
    df_richieste_mag = scarica_da_sheet("Richieste_Preventivo_Magazzino")
    df_preventivi = scarica_da_sheet("Registro_Preventivi")
    df_fornitori = scarica_da_sheet("Anagrafica_Fornitori")
    
    if df_richieste_mag.empty:
        st.info("📦 Nessuna richiesta di acquisto inoltrata dai magazzini al momento.")
        return
        
    if df_preventivi.empty:
        df_preventivi = pd.DataFrame(columns=["id_preventivo", "id_richiesta_mag", "fornitore", "importo_ivato", "data_inserimento", "stato_approvazione", "note"])
    if df_fornitori.empty:
        df_fornitori = pd.DataFrame([{"id_fornitore": "F01", "ragione_sociale": "Forniture Rossi Srl", "partita_iva": "01234567890", "email_contatto": "info@rossi.it"}])
        carica_su_sheet(df_fornitori, "Anagrafica_Fornitori")

    richieste_attive = df_richieste_mag[df_richieste_mag["stato_iter"] == "In attesa di preventivi"]
    
    if richieste_attive.empty:
        st.success("✅ Tutte le richieste del magazzino sono state evase o hanno un preventivo associato.")
    else:
        opzioni_rm = [f"REQ {r['id_richiesta_mag']} [{r['magazzino_origine']}]: {r['materiale_richiesto']}" for _, r in richieste_attive.iterrows()]
        scelta = st.selectbox("Seleziona il fabbisogno del magazzino da girare al fornitore:", opzioni_rm)
        id_rm_scelto = scelta.split(" ")[1]
        
        fornitore_scelto = st.selectbox("Ditta Fornitrice:", df_fornitori["ragione_sociale"].tolist())
        
        with st.form("form_salva_prev"):
            importo = st.number_input("Costo Preventivato (€, IVA Inclusa):", min_value=0.0)
            note_p = st.text_input("Riferimento preventivo / Note:")
            if st.form_submit_button("Collega ed Invia Preventivo a Registro"):
                if importo > 0:
                    id_p = 7001 if df_preventivi.empty else int(pd.to_numeric(df_preventivi["id_preventivo"], errors='coerce').max()) + 1
                    nuovo = pd.DataFrame([{"id_preventivo": id_p, "id_richiesta_mag": id_rm_scelto, "fornitore": fornitore_scelto, "importo_ivato": f"{importo:.2f}", "data_inserimento": datetime.now().strftime("%d/%m/%Y %H:%M"), "stato_approvazione": "In attesa di validazione Dirigente", "note": note_p.strip()}])
                    df_richieste_mag.loc[df_richieste_mag["id_richiesta_mag"].astype(str) == str(id_rm_scelto), "stato_iter"] = "Preventivo Ricevuto"
                    carica_su_sheet(pd.concat([df_preventivi, nuovo], ignore_index=True), "Registro_Preventivi")
                    carica_su_sheet(df_richieste_mag, "Richieste_Preventivo_Magazzino")
                    st.success("Preventivo agganciato con successo!")
                    st.rerun()

    st.markdown("### 📜 Riepilogo Richieste Interne Magazzini")
    st.dataframe(df_richieste_mag, use_container_width=True, hide_index=True)
