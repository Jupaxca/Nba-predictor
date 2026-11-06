import streamlit as st
import pandas as pd
import json
from nba_api.stats.static import teams, players
from nba_predictor import cargar_datos, analizar

st.set_page_config(
    page_title="NBAMetrics Pro",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Oswald:wght@600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        background-color: #070a12;
        color: #f3f4f6;
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 1250px;
    }

    .hero-box {
        background: linear-gradient(145deg, #0f172a 0%, #070a12 100%);
        padding: 32px 24px;
        border-radius: 16px;
        color: white;
        text-align: center;
        border: 1px solid #1e293b;
        margin-bottom: 24px;
        position: relative;
        overflow: hidden;
    }
    .hero-box::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0; height: 4px;
        background: linear-gradient(90deg, #17408b 0%, #c9082a 50%, #f59e0b 100%);
    }

    .hero-title {
        font-family: 'Oswald', sans-serif;
        font-weight: 700;
        font-size: 36px;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        margin: 0;
        background: linear-gradient(90deg, #ffffff 60%, #cbd5e1 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .nba-card {
        background-color: #0f172a;
        border: 1px solid #1e293b;
        border-radius: 14px;
        padding: 22px;
        margin-bottom: 20px;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.35);
    }

    .pill-badge {
        display: inline-block;
        padding: 5px 12px;
        border-radius: 999px;
        font-size: 0.82rem;
        font-weight: 600;
    }
    .pill-blue {
        background: rgba(23, 64, 139, 0.25);
        color: #60a5fa;
        border: 1px solid rgba(59, 130, 246, 0.4);
    }

    [data-testid="stMetricValue"] {
        font-family: 'Oswald', sans-serif;
        font-size: 1.8rem;
        font-weight: 700;
        color: #f8fafc;
    }
    [data-testid="stMetricLabel"] {
        color: #94a3b8;
        font-size: 0.85rem;
    }

    .stButton button[kind="primary"] {
        background: linear-gradient(135deg, #c9082a 0%, #990620 100%);
        color: white;
        border: none;
        border-radius: 10px;
        font-weight: 700;
        font-size: 1rem;
        padding: 0.6rem 1.2rem;
        box-shadow: 0 4px 14px rgba(201, 8, 42, 0.35);
    }
    .stButton button[kind="primary"]:hover {
        background: linear-gradient(135deg, #e11d48 0%, #b91c1c 100%);
        box-shadow: 0 6px 18px rgba(225, 29, 72, 0.5);
    }

    .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] {
        border-radius: 8px !important;
        background-color: #070a12 !important;
        border-color: #1e293b !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

@st.cache_data
def obtener_diccionario_equipos():
    lista = teams.get_teams()
    lista_ordenada = sorted(lista, key=lambda x: x['full_name'])
    return {t['full_name']: {'abbrev': t['abbreviation'], 'id': t['id']} for t in lista_ordenada}

@st.cache_data
def obtener_lista_completa_jugadores():
    try:
        activos = players.get_active_players()
        nombres = sorted([p['full_name'] for p in activos])
        if nombres:
            return nombres
    except Exception:
        pass
    return [
        "LeBron James", "Luka Doncic", "Stephen Curry", "Giannis Antetokounmpo",
        "Nikola Jokic", "Jayson Tatum", "Shai Gilgeous-Alexander", "Anthony Edwards",
        "Kevin Durant", "Anthony Davis", "Kyrie Irving", "Donovan Mitchell", "Jalen Brunson"
    ]

equipos_dict = obtener_diccionario_equipos()
nombres_equipos = list(equipos_dict.keys())
lista_jugadores_global = obtener_lista_completa_jugadores()

st.markdown(
    """
    <div class="hero-box">
        <div class="hero-title">NBAMetrics Pro</div>
        <p style="font-size: 14px; color: #94a3b8; margin-top: 6px; margin-bottom: 0;">
            Motor cuantitativo de proyección individual multimétrica
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="nba-card">', unsafe_allow_html=True)
st.subheader(" Configuración del Partido y Mercado")

col1, col2, col3 = st.columns(3)

with col1:
    idx_lebron = lista_jugadores_global.index("LeBron James") if "LeBron James" in lista_jugadores_global else 0
    jugador = st.selectbox(
        "1. Jugador a analizar (Escribe para buscar)",
        options=lista_jugadores_global,
        index=idx_lebron,
        key="sel_jugador_global"
    )

with col2:
    idx_gsw = nombres_equipos.index("Golden State Warriors") if "Golden State Warriors" in nombres_equipos else 0
    equipo_rival_nombre = st.selectbox("2. Equipo Rival", nombres_equipos, index=idx_gsw, key="sel_equipo_rival")
    rival_abrev = equipos_dict[equipo_rival_nombre]['abbrev']

with col3:
    local = st.checkbox("Juega de Local", value=True)
    playoffs = st.checkbox("Es Partido de Playoffs", value=False)

with st.expander(" Parámetros Avanzados y Cuotas de Mercado (Opcional)", expanded=False):
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        spread = st.number_input("Handicap / Spread (Favorito -4.5)", value=0.0, step=0.5)
        minutos_override = st.number_input("Minutos Proyectados (0 = Automático)", value=0.0, step=1.0)
    with col_b:
        cuota_over = st.number_input("Cuota Over Decimal (Ej. 1.90)", value=0.0, step=0.05)
    with col_c:
        cuota_under = st.number_input("Cuota Under Decimal (Ej. 1.90)", value=0.0, step=0.05)

ejecutar = st.button("Analizar Todas las Estadísticas", type="primary", use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

if ejecutar:
    try:
        with st.spinner(f"Analizando métricas e historial de {jugador} vs {rival_abrev}..."):
            datos = cargar_datos(jugador, ["2025-26", "2026-27"], incluir_playoffs=playoffs)
            
            metricas_lista = [
                ("PTS", "Puntos", 24.5),
                ("REB", "Rebotes", 7.5),
                ("AST", "Asistencias", 7.5),
                ("PRA", "Puntos + Rebotes + Asistencias", 39.5),
                ("PR", "Puntos + Rebotes", 31.5),
                ("PA", "Puntos + Asistencias", 31.5),
                ("RA", "Rebotes + Asistencias", 14.5),
                ("FG3M", "Triples Anotados", 2.5),
                ("STL", "Robos", 1.5),
                ("BLK", "Tapones", 0.5)
            ]
            
            resultados = []
            
            for codigo_m, nombre_m, linea_def in metricas_lista:
                res = analizar(
                    datos=datos,
                    metrica=codigo_m,
                    linea=linea_def,
                    rival=rival_abrev,
                    local=local,
                    playoffs=playoffs,
                    minutos_override=minutos_override if minutos_override > 0 else None,
                    spread=spread if spread != 0.0 else None,
                    cuota_over=cuota_over if cuota_over > 0 else None,
                    cuota_under=cuota_under if cuota_under > 0 else None
                )
                res["nombre_largo"] = nombre_m
                resultados.append(res)

        st.markdown('<div class="nba-card">', unsafe_allow_html=True)
        
        st.markdown(
            f"""
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h3 style="margin: 0;">Reporte Integral: {jugador} vs {equipo_rival_nombre} ({rival_abrev})</h3>
                <span class="pill-badge pill-blue">Minutos proyectados: {resultados[0]['minutos_proyectados']} min</span>
            </div>
            """,
            unsafe_allow_html=True
        )

        tabla_resumen = []
        for r in resultados:
            fila = {
                "Estadística": r["nombre_largo"],
                "Código": r["metrica"],
                "Proyección": r["proyeccion_modelo"],
                "Piso (P15)": r["escenarios"]["mal_juego_P15"],
                "Techo (P85)": r["escenarios"]["techo_P85"]
            }
            if "analisis_apuesta" in r:
                fila["Recomendación"] = f"{r['analisis_apuesta']['lado']} (EV: {r['analisis_apuesta']['EV']*100:.1f}%)"
            tabla_resumen.append(fila)
            
        df_tabla = pd.DataFrame(tabla_resumen)
        st.dataframe(df_tabla, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader(" Desglose Detallado por Categoría")

        cols = st.columns(3)
        for idx, r in enumerate(resultados):
            with cols[idx % 3]:
                extra_html = ""
                if "analisis_apuesta" in r:
                    ap = r["analisis_apuesta"]
                    color_rec = "#34d399" if ap["recomendacion"] == "APOSTAR" else "#94a3b8"
                    extra_html = f"<div style='font-size: 0.78rem; color: {color_rec}; margin-top: 4px;'>Apuesta: <b>{ap['lado']}</b> (EV: {ap['EV']*100:.1f}%)</div>"

                st.markdown(
                    f"""
                    <div style="background-color: #070a12; border: 1px solid #1e293b; border-radius: 10px; padding: 14px; margin-bottom: 14px;">
                        <div style="font-size: 0.85rem; color: #94a3b8; font-weight: 600;">{r['nombre_largo']} ({r['metrica']})</div>
                        <div style="font-family: 'Oswald', sans-serif; font-size: 2.2rem; font-weight: 700; color: #f8fafc; margin: 4px 0;">{r['proyeccion_modelo']}</div>
                        <div style="font-size: 0.8rem; color: #64748b;">Rango estocástico: {r['escenarios']['mal_juego_P15']} a {r['escenarios']['techo_P85']}</div>
                        {extra_html}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        st.markdown("</div>", unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Error durante el procesamiento: {e}")
