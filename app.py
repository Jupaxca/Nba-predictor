import streamlit as st
from nba_predictor import cargar_datos, analizar

st.set_page_config(page_title="Predicciones NBA", layout="centered")

st.title("Modelo Predictivo NBA")
st.write("Análisis estadístico individual con Machine Learning y Monte Carlo")

jugador = st.text_input("Nombre del jugador", "LeBron James")
metrica = st.selectbox("Estadística a analizar", ["PTS", "REB", "AST", "PRA", "PR", "PA", "RA", "FG3M", "STL", "BLK"])
linea = st.number_input("Línea de apuesta", value=25.5, step=0.5)
rival = st.text_input("Abreviatura del equipo rival", "GSW")
local = st.checkbox("Juega de local", value=True)

if st.button("Ejecutar Análisis"):
    if jugador and rival:
        try:
            with st.spinner("Entrenando el modelo y calculando probabilidades"):
                datos = cargar_datos(jugador, ["2024-25", "2025-26"], incluir_playoffs=True)
                
                resultado = analizar(
                    datos=datos,
                    metrica=metrica,
                    linea=linea,
                    rival=rival.upper(),
                    local=local
                )
                
                st.success("Cálculo finalizado exitosamente")
                
                col1, col2 = st.columns(2)
                col1.metric("Proyección del Modelo", f"{resultado['proyeccion_modelo']} {metrica}")
                col2.metric("Probabilidad Over", f"{resultado['probabilidad_over']:.1f}%")
                
                st.subheader("Escenarios Simulados")
                st.write("Piso estadístico (Percentil 15) ", resultado['escenarios']['mal_juego_P15'])
                st.write("Techo estadístico (Percentil 85) ", resultado['escenarios']['techo_P85'])
                
                st.subheader("Pesos del Ensamble")
                st.json(resultado['pesos_ensamble'])
                
                st.subheader("Reporte Completo")
                st.json(resultado)
                
        except Exception as e:
            st.error(f"Ocurrió un error al procesar los datos {e}")
    else:
        st.warning("Por favor ingresa el nombre del jugador y el rival")
