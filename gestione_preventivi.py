import streamlit as st
import pandas as pd
from datetime import datetime

def mostra_interfaccia_preventivi(scarica_da_sheet, carica_su_sheet, invia_email_sistema, url_intermediario, df_istanze):
    st.markdown("## 📊 Hub Indipendente: Preventivi e Richieste di Acquisto Magazzino")
    st.markdown("Questa sezione gestisce in modo autonomo le richieste di fornitura generate direttamente dal magazzino e i relativi preventivi associati.")
    
    # --- CARICAMENTO REPERTORI COERENTI ---
    df_richieste_mag = scarica_da_sheet("Richieste_Preventivo_Magazzino")
    df_preventivi = scarica_da_sheet("Registro_Preventivi")
    df_fornitori = scarica_da_sheet("Anagrafica_Fornitori")
    
    # Inizializzazione strutture se vuote
    if df_richieste_mag.empty:
        df_richieste_mag = pd.DataFrame(columns=[
            "id_richiesta_mag", "data_creazione", "magazzino_origine", 
            "materiale_richiesto", "quantita_esimata", "stato_iter", "note"
        ])
    if df_preventivi.empty:
        df_preventivi = pd.DataFrame(columns=[
            "id_preventivo", "id_richiesta_mag", "fornitore", 
            "importo_ivato", "data_inserimento", "stato_approvazione", "note"
        ])
    if df_fornitori.empty:
        df_fornitori = pd.DataFrame([
            {"id_fornitore": "F01", "ragione_sociale": "Forniture Scolastiche Rossi Srl", "partita_iva": "01234567890", "email_contatto": "commerciale@rossiforniture.it"},
            {"id_fornitore": "F02", "ragione_sociale": "Informatica & Digitale SpA", "partita_iva": "09876543210", "email_contatto": "info@informaticadigitale.it"}
        ])
        carica_su_sheet(df_fornitori, "Anagrafica_Fornitori")

    # Organizzazione dei pannelli di lavoro
    tab_crea_richiesta, tab_associa_prev, tab_registro_completo, tab_fornitori = st.tabs([
        "📦 1. Nuova Richiesta dal Magazzino",
        "✍️ 2. Associa Preventivo Fornitore",
        "📜 3. Registro Generale Acquisti",
        "🏢 4. Anagrafica Fornitori"
    ])

    # ==========================================
    # TAB 1: NUOVA RICHIESTA DAL MAGAZZINO
    # ==========================================
    with tab_crea_richiesta:
        st.markdown("### 🏬 Formula Nuova Richiesta di Approvvigionamento")
        st.markdown("Inserisci una necessità nata direttamente dalla gestione dei magazzini d'Istituto.")
        
        with st.form("form_nuova_richiesta_mag"):
            mag_orig = st.selectbox("Magazzino richiedente:", ["Personale ATA", "Officina", "Tecnici Informatici", "Ufficio Tecnico Generale"])
            mat_richiesto = st.text_input("Descrizione Materiale / Bene da acquistare (es. 50 Risme Carta A4):")
            qta_est = st.text_input("Quantità o Specifiche Tecniche stimate:")
            note_rich = st.text_area("Note interne o urgenza:")
            
            submit_richiesta = st.form_submit_button("Invia Richiesta al Registro Acquisti", use_container_width=True)
            
            if submit_richiesta:
                if mat_richiesto.strip():
                    try:
                        id_r_num = pd.to_numeric(df_richieste_mag["id_richiesta_mag"], errors='coerce')
                        nuovo_id_rm = int(id_r_num.max()) + 1 if not df_richieste_mag.empty and not id_r_num.dropna().empty else 2001
                    except Exception:
                        nuovo_id_rm = 2001
                        
                    nuova_r_mag = pd.DataFrame([{
                        "id_richiesta_mag": nuovo_id_rm,
                        "data_creazione": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "magazzino_origine": mag_orig,
                        "materiale_richiesto": mat_richiesto.strip(),
                        "quantita_esimata": qta_est.strip(),
                        "stato_iter": "In attesa di preventivi",
                        "note": note_rich.strip()
                    }])
                    
                    df_richieste_mag_agg = pd.concat([df_richieste_mag, nuova_r_mag], ignore_index=True)
                    carica_su_sheet(df_richieste_mag_agg, "Richieste_Preventivo_Magazzino")
                    st.success(f"✅ Richiesta interna d'acquisto registrata con ID: {nuovo_id_rm}")
                    st.rerun()
                else:
                    st.error("Il campo 'Descrizione Materiale' è obbligatorio.")

    # ==========================================
    # TAB 2: ASSOCIA PREVENTIVO FORNITORE
    # ==========================================
    with tab_associa_prev:
        st.markdown("### 💸 Collega Offerta Economica Ricevuta")
        
        # Mostriamo solo le richieste create dal magazzino che sono in attesa di offerte
        richieste_attive = df_richieste_mag[df_richieste_mag["stato_iter"] == "In attesa di preventivi"] if not df_richieste_mag.empty else pd.DataFrame()
        
        if richieste_attive.empty:
            st.info("Nessuna richiesta del magazzino è attualmente scoperta o in attesa di preventivo.")
        else:
            opzioni_rm = []
            mappa_rm = {}
            for _, riga in richieste_attive.iterrows():
                label = f"REQ {riga['id_richiesta_mag']} - {riga['magazzino_origine']}: {riga['materiale_richiesto']}"
                opzioni_rm.append(label)
                mappa_rm[label] = riga['id_richiesta_mag']
                
            richiesta_selezionata = st.selectbox("Seleziona la richiesta del magazzino di riferimento:", opzioni_rm)
            id_rm_scelto = mappa_rm[richiesta_selezionata]
            
            lista_f = df_fornitori["ragione_sociale"].tolist() if not df_fornitori.empty else ["Nessun fornitore censito"]
            fornitore_scelto = st.selectbox("Ditta / Operatore Economico offerente:", lista_f)
            
            with st.form("form_collega_preventivo"):
                col1, col2 = st.columns(2)
                with col1:
                    importo = st.number_input("Costo Totale Offerto (€, con IVA):", min_value=0.0, step=10.0, format="%.2f")
                with col2:
                    note_p = st.text_input("Riferimento preventivo cartaceo o note:")
                    
                submit_p = st.form_submit_button("Abbinate Preventivo alla Richiesta", use_container_width=True)
                
                if submit_p:
                    if fornitore_scelto == "Nessun fornitore censito":
                        st.error("Censisci prima un'azienda nel tab dedicato.")
                    elif importo <= 0:
                        st.error("Inserisci un importo valido.")
                    else:
                        try:
                            id_p_num = pd.to_numeric(df_preventivi["id_preventivo"], errors='coerce')
                            nuovo_id_p = int(id_p_num.max()) + 1 if not df_preventivi.empty and not id_p_num.dropna().empty else 7001
                        except Exception:
                            nuovo_id_p = 7001
                            
                        nuovo_prev = pd.DataFrame([{
                            "id_preventivo": nuovo_id_p,
                            "id_richiesta_mag": id_rm_scelto,
                            "fornitore": fornitore_scelto,
                            "importo_ivato": f"{importo:.2f}",
                            "data_inserimento": datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "stato_approvazione": "Pronto per validazione Dirigente/DSGA",
                            "note": note_p.strip()
                        }])
                        
                        # Aggiorniamo lo stato della richiesta interna
                        df_richieste_mag.loc[df_richieste_mag["id_richiesta_mag"].astype(str) == str(id_rm_scelto), "stato_iter"] = "Preventivo Ricevuto"
                        
                        carica_su_sheet(pd.concat([df_preventivi, nuovo_prev], ignore_index=True), "Registro_Preventivi")
                        carica_su_sheet(df_richieste_mag, "Richieste_Preventivo_Magazzino")
                        
                        st.success(f"🎉 Preventivo ID {nuovo_id_p} registrato e associato alla richiesta interna REQ {id_rm_scelto}!")
                        st.rerun()

    # ==========================================
    # TAB 3: REGISTRO GENERALE ACQUISTI
    # ==========================================
    with tab_registro_completo:
        st.markdown("### 📋 Registro Fabbisogni ed Esiti Economici")
        st.markdown("#### 🔹 Richieste Interne Generate dai Magazzini")
        st.dataframe(df_richieste_mag, use_container_width=True, hide_index=True)
        
        st.markdown("#### 🔸 Preventivi Economici Ricevuti dalle Ditte")
        st.dataframe(df_preventivi, use_container_width=True, hide_index=True)

    # ==========================================
    # TAB 4: ANAGRAFICA FORNITORI
    # ==========================================
    with tab_fornitori:
        st.markdown("### 🏢 Elenco Ditte Partner Accreditate")
        st.dataframe(df_fornitori, use_container_width=True, hide_index=True)
        
        with st.expander("➕ Aggiungi un nuovo Fornitore all'Albo"):
            with st.form("form_f_nuovo"):
                r_s = st.text_input("Ragione Sociale:")
                p_i = st.text_input("Partita IVA:")
                em = st.text_input("Email/PEC:")
                if st.form_submit_button("Inserisci Azienda"):
                    if r_s.strip() and p_i.strip():
                        nuovo_f = pd.DataFrame([{"id_fornitore": f"F{len(df_fornitori)+1:02d}", "ragione_sociale": r_s.strip(), "partita_iva": p_i.strip(), "email_contatto": em.strip()}])
                        carica_su_sheet(pd.concat([df_fornitori, nuovo_f], ignore_index=True), "Anagrafica_Fornitori")
                        st.success("Azienda registrata!")
                        st.rerun()
