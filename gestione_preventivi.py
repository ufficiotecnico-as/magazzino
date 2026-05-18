import streamlit as st
import pandas as pd
from datetime import datetime
import json

def mostra_interfaccia_preventivi(scarica_da_sheet, carica_su_sheet, invia_email_sistema, URL_INTERMEDIARIO_SILENZIOSO, df_istanze, genera_pdf_ordine_fornitore, carica_su_drive_unico, ID_CARTELLA_ORDINI):
    st.markdown("## 📊 Hub Gestione Fornitori & Tracciabilità Preventivi")
    
    tab_richieste, tab_rubrica, tab_inserimento, tab_registro_finito = st.tabs([
        "📥 Fabbisogni dai Magazzini",
        "📙 Rubrica Anagrafica Fornitori", 
        "✍️ Inserisci Offerta / Preventivo Ricevuto", 
        "📜 Registro Storico Preventivi"
    ])
    
    df_fabbisogni = scarica_da_sheet("Richieste_Preventivo_Magazzino")
    df_preventivi = scarica_da_sheet("Registro_Preventivi")
    df_fornitori = scarica_da_sheet("Anagrafica_Fornitori")
    
    # --- TAB 1: FABBISOGNI ---
    with tab_richieste:
        st.markdown("### Elenco dei materiali segnalati dai capigruppo logistici")
        st.write("Queste richieste necessitano dell'acquisizione di preventivi.")
        
        if not df_fabbisogni.empty and "materiale_richiesto" in df_fabbisogni.columns:
            df_fabbisogni_attivi = df_fabbisogni[df_fabbisogni["materiale_richiesto"].astype(str).str.strip() != ""]
        else:
            df_fabbisogni_attivi = pd.DataFrame(columns=["id_richiesta_mag", "magazzino_origine", "materiale_richiesto", "quantita_richiesta", "data_segnalazione", "stato_iter"])
        
        if df_fabbisogni_attivi.empty:
            st.info("Nessuna segnalazione aperta.")
        else:
            st.dataframe(df_fabbisogni_attivi, use_container_width=True, hide_index=True)
            
    # --- TAB 2: RUBRICA ---
    with tab_rubrica:
        st.markdown("### 📙 Gestione Rubrica Fornitori d'Istituto")
        
        with st.expander("➕ Salva un nuovo Fornitore in Rubrica", expanded=False):
            with st.form("form_nuovo_fornitore"):
                rag_soc = st.text_input("Ragione Sociale / Denominazione Ditta:")
                p_iva = st.text_input("Partita IVA / Codice Fiscale Fornitore:")
                indirizzo_completo = st.text_input("Indirizzo Sede Legale (Via, CAP, Città, Prov):")
                email_cont = st.text_input("Email o PEC di contatto:")
                
                if st.form_submit_button("💾 Salva Fornitore in Rubrica", use_container_width=True):
                    if not rag_soc.strip() or not p_iva.strip():
                        st.error("I campi Ragione Sociale e Partita IVA sono obbligatori.")
                    else:
                        if not df_fornitori.empty and "id_fornitore" in df_fornitori.columns:
                            id_forn_num = pd.to_numeric(df_fornitori["id_fornitore"], errors='coerce')
                            id_forn = int(id_forn_num.max() + 1) if not id_forn_num.dropna().empty else 1
                        else:
                            id_forn = 1
                        
                        nuovo_forn_df = pd.DataFrame([{
                            "id_fornitore": str(id_forn),
                            "ragione_sociale": str(rag_soc.strip()),
                            "partita_iva": str(p_iva.strip()),
                            "indirizzo": str(indirizzo_completo.strip()),
                            "email_contatto": str(email_cont.strip())
                        }])
                        df_fornitori = pd.concat([df_fornitori, nuovo_forn_df], ignore_index=True)
                        carica_su_sheet(df_fornitori, "Anagrafica_Fornitori")
                        st.success(f"Ditta '{rag_soc.strip()}' registrata!")
                        st.rerun()
                        
        if not df_fornitori.empty and "ragione_sociale" in df_fornitori.columns:
            df_fornitori_attivi = df_fornitori[df_fornitori["ragione_sociale"].astype(str).str.strip() != ""]
        else:
            df_fornitori_attivi = pd.DataFrame(columns=["id_fornitore", "ragione_sociale", "partita_iva", "indirizzo", "email_contatto"])
            
        if df_fornitori_attivi.empty:
            st.info("Nessun fornitore in anagrafica.")
        else:
            st.dataframe(df_fornitori_attivi, use_container_width=True, hide_index=True)

    # --- TAB 3: INSERIMENTO ---
    with tab_inserimento:
        st.markdown("### Collega un preventivo economico ricevuto a una richiesta interna")
        
        if not df_fabbisogni.empty and "materiale_richiesto" in df_fabbisogni.columns:
            df_fabbisogni_attivi = df_fabbisogni[df_fabbisogni["materiale_richiesto"].astype(str).str.strip() != ""]
        else:
            df_fabbisogni_attivi = pd.DataFrame()
            
        if not df_fornitori.empty and "ragione_sociale" in df_fornitori.columns:
            df_fornitori_attivi = df_fornitori[df_fornitori["ragione_sociale"].astype(str).str.strip() != ""]
        else:
            df_fornitori_attivi = pd.DataFrame()
        
        if df_fabbisogni_attivi.empty:
            st.warning("Nessuna richiesta aperta.")
        elif df_fornitori_attivi.empty:
            st.error("⚠️ Nessun fornitore in rubrica.")
        else:
            lista_fabbisogni = [f"ID {r['id_richiesta_mag']} - {r['materiale_richiesto']} ({r['magazzino_origine']})" for _, r in df_fabbisogni_attivi.iterrows()]
            scelta_fabb = st.selectbox("Seleziona il fabbisogno d'origine:", lista_fabbisogni)
            id_fabb_scelto = scelta_fabb.split(" - ")[0].replace("ID ", "").strip()
            
            with st.form("form_aggiunta_preventivo"):
                mappa_nomi = {f"{f['ragione_sociale']} (P.IVA: {f['partita_iva']})": f for _, f in df_fornitori_attivi.iterrows()}
                fornitore_selezionato_rubrica = st.selectbox("Scegli la ditta:", list(mappa_nomi.keys()))
                importo_lordo = st.number_input("Importo Totale Stimato IVATO (€):", min_value=0.0, step=0.01)
                note_preventivo = st.text_area("Note aggiuntive:")
                
                if st.form_submit_button("Registra preventivo a sistema"):
                    f_dati = mappa_nomi[fornitore_selezionato_rubrica]
                    blocco_spett_le = f"{f_dati['ragione_sociale']}\nSede Legale: {f_dati['indirizzo']}\nP.IVA / C.F.: {f_dati['partita_iva']}\nContatto: {f_dati['email_contatto']}"
                    
                    if not df_preventivi.empty and "id_preventivo" in df_preventivi.columns:
                        id_prev_num = pd.to_numeric(df_preventivi["id_preventivo"], errors='coerce')
                        id_prev_nuovo = 501 if id_prev_num.dropna().empty else int(id_prev_num.max()) + 1
                    else:
                        id_prev_nuovo = 501
                    
                    nuovo_prev_df = pd.DataFrame([{
                        "id_preventivo": str(id_prev_nuovo),
                        "id_richiesta_mag": str(id_fabb_scelto),
                        "fornitore": blocco_spett_le,
                        "importo_ivato": f"{importo_lordo:.2f}",
                        "data_inserimento": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "stato_approvazione": "In valutazione",
                        "note": note_preventivo.strip(),
                        "cig": "",
                        "determina": ""
                    }])
                    df_prev_finale = pd.concat([df_preventivi, nuovo_prev_df], ignore_index=True)
                    carica_su_sheet(df_prev_finale, "Registro_Preventivi")
                    st.success(f"Preventivo salvato!")
                    st.rerun()
                        
    # --- TAB 4: STORICO E LETTERA ORDINE ---
    with tab_registro_finito:
        st.markdown("### Valutazione, Dettaglio Articoli ed Emissione Lettera d'Ordine")
        
        if not df_preventivi.empty and "id_preventivo" in df_preventivi.columns:
            df_preventivi_validi = df_preventivi[df_preventivi["id_preventivo"].astype(str).str.strip() != ""]
        else:
            df_preventivi_validi = pd.DataFrame(columns=["id_preventivo", "id_richiesta_mag", "fornitore", "importo_ivato", "data_inserimento", "stato_approvazione", "note", "cig", "determina"])
        
        if df_preventivi_validi.empty:
            st.info("Nessun preventivo presente.")
        else:
            st.dataframe(df_preventivi_validi, use_container_width=True, hide_index=True)
            st.markdown("---")
            
            if "stato_approvazione" in df_preventivi_validi.columns:
                preventivi_valutabili = df_preventivi_validi[df_preventivi_validi["stato_approvazione"] == "In valutazione"]
            else:
                preventivi_valutabili = pd.DataFrame()
                
            if preventivi_valutabili.empty:
                st.info("Nessun preventivo da elaborare.")
            else:
                st.markdown("#### ⚙️ Configura Voci di Dettaglio ed Emetti Ordine")
                opzioni_preventivo = [f"PREV ID {p['id_preventivo']} - {p['fornitore'].splitlines()[0]} (€ {p['importo_ivato']})" for _, p in preventivi_valutabili.iterrows()]
                scelta_p = st.selectbox("Seleziona il preventivo da emettere:", opzioni_preventivo)
                id_p_scelto = scelta_p.split(" - ")[0].replace("PREV ID ", "").strip()
                
                riga_p = df_preventivi_validi[df_preventivi_validi["id_preventivo"].astype(str) == str(id_p_scelto)].iloc[0]
                
                if "numero_righe_articoli" not in st.session_state:
                    st.session_state.numero_righe_articoli = 1
                
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("➕ Aggiungi Riga Articolo", use_container_width=True):
                        st.session_state.numero_righe_articoli += 1
                with col_btn2:
                    if st.button("➖ Rimuovi Ultima Riga", use_container_width=True) and st.session_state.numero_righe_articoli > 1:
                        st.session_state.numero_righe_articoli -= 1
                
                lista_articoli = []
                totale_calcolato = 0.0
                
                for i in range(st.session_state.numero_righe_articoli):
                    st.markdown(f"**Articolo {i+1}**")
                    c_desc, c_qta, c_prezzo = st.columns([2, 0.5, 1])
                    with c_desc:
                        desc_art = st.text_input(f"Descrizione Prodotto", key=f"art_desc_{i}")
                    with c_qta:
                        qta_art = st.number_input(f"Q.tà", min_value=1, value=1, key=f"art_qta_{i}")
                    with c_prezzo:
                        prezzo_art = st.number_input(f"Prezzo Unitario IVATO (€)", min_value=0.0, step=0.01, key=f"art_pr_{i}")
                    
                    tot_riga = qta_art * prezzo_art
                    totale_calcolato += tot_riga
                    
                    lista_articoli.append({
                        "descrizione": desc_art,
                        "descrizione_materiale": desc_art,
                        "quantita": qta_art,
                        "prezzo_unitario": f"{prezzo_art:.2f}",
                        "totale_riga": f"{tot_riga:.2f}"
                    })
                
                st.markdown(f"### 💰 Totale: **{totale_calcolato:.2f} €**")
                
                c1, c2 = st.columns(2)
                with c1:
                    cig_input = st.text_input("Codice CIG:", placeholder="Es. Z1A3C4D5E6")
                    determina_input = st.text_input("Numero/Anno Determina:", placeholder="Es. 145/2026")
                    data_prev_forn = st.text_input("Data invio preventivo:", value=datetime.now().strftime("%d/%m/%Y"))
                with c2:
                    prot_forn = st.text_input("Protocollo ditta:", value="N.D.")
                    prot_inst = st.text_input("Protocollo ingresso:", placeholder="Es. 0004120/E")
                
                if not df_fabbisogni.empty and "id_richiesta_mag" in df_fabbisogni.columns:
                    riga_fabb = df_fabbisogni[df_fabbisogni["id_richiesta_mag"].astype(str) == str(riga_p["id_richiesta_mag"])]
                else:
                    riga_fabb = pd.DataFrame()
                
                if st.button("🔴 GENERA LETTERA D'ORDINE", type="primary", use_container_width=True):
                    errori = False
                    for art in lista_articoli:
                        if not art["descrizione"].strip(): errori = True
                    if errori or not cig_input.strip() or not determina_input.strip() or not prot_inst.strip():
                        st.error("Campi obbligatori mancanti.")
                    else:
                        mappa_dati_pdf = {
                            "fornitore": riga_p["fornitore"],
                            "oggetto_ordine": f"Affidamento directo fornitura materiale - ID {riga_p['id_richiesta_mag']}",
                            "data_preventivo": data_prev_forn,
                            "protocollo_fornitore": prot_forn,
                            "protocollo_istituto": prot_inst,
                            "articoli": lista_articoli,
                            "importo_ivato": f"{totale_calcolato:.2f}",
                            "cig": cig_input.strip().upper(),
                            "determina": determina_input.strip()
                        }
                        
                        idx_p = df_preventivi.index[df_preventivi["id_preventivo"].astype(str) == str(id_p_scelto)].tolist()[0]
                        df_preventivi.at[idx_p, "stato_approvazione"] = "Approvato ed Emesso"
                        df_preventivi.at[idx_p, "cig"] = cig_input.strip().upper()
                        df_preventivi.at[idx_p, "determina"] = determina_input.strip()
                        df_preventivi.at[idx_p, "note"] = f"{riga_p['note']} | Articoli: " + json.dumps(lista_articoli)
                        carica_su_sheet(df_preventivi, "Registro_Preventivi")
                        
                        if not riga_fabb.empty:
                            idx_f = df_fabbisogni.index[df_fabbisogni["id_richiesta_mag"].astype(str) == str(riga_p["id_richiesta_mag"])].tolist()[0]
                            df_fabbisogni.at[idx_f, "stato_iter"] = "Ordinato / Evaso"
                            carica_su_sheet(df_fabbisogni, "Richieste_Preventivo_Magazzino")
                        
                        pdf_bytes = genera_pdf_ordine_fornitore(mappa_dati_pdf)
                        nome_file_generato = f"Lettera_Ordine_PREV_{id_p_scelto}.pdf"
                        
                        carica_su_drive_unico(pdf_bytes, nome_file_generato, "application/pdf", ID_CARTELLA_ORDINI)
                        
                        st.download_button(
                            label="📥 Scarica Copia Locale Lettera d'Ordine (PDF)",
                            data=pdf_bytes,
                            file_name=nome_file_generato,
                            mime="application/pdf",
                            use_container_width=True
                        )
                        st.session_state.numero_righe_articoli = 1
                        st.balloons()
