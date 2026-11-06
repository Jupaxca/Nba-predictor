import streamlit as st
import json
from nba_predictor import cargar_datos, analizar

st.set_page_config(
    page_title="NBAMetrics Pro",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------
# CSS GLOBAL — Estilo Visual NBA (Obsidiana, Azul & Rojo NBA, Dorado)
# ---------------------------------------------------------------------
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
        max-width: 1200px;
    }

    /* Hero Header */
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

    /* Cards */
    .nba-card {
        background-color: #0f172a;
        border: 1px solid #1e293b;
        border-radius: 14px;
        padding: 22px;
        margin-bottom: 20px;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.35);
    }

    /* Custom Badges */
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
    .pill-green {
        background: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.35);
    }
    .pill-red {
        background: rgba(201, 8, 42, 0.18);
        color: #f87171;
        border: 1px solid rgba(201, 8, 42, 0.4);
    }

    /* Metrics override */
    [data-testid="stMetricValue"] {
        font-family: 'Oswald', sans-serif;
        font-size: 2rem;
        font-weight: 700;
        color: #f8fafc;
    }
    [data-testid="stMetricLabel"] {
        color: #94a3b8;
        font-size: 0.88rem;
    }

    /* Primary Button Gradient */
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

    /* Inputs */
    .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] {
        border-radius: 8px !important;
        background-color: #070a12 !important;
        border-color: #1e293b !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------
# HEADER PRINCIPAL
# ---------------------------------------------------------------------
st.markdown(
    """
    <div class="hero-box">
        <div class="hero-title">NBAMetrics Pro</div>
        <p style="font-size: 14px; color: #94a3b8; margin-top: 6px; margin-bottom: 0;">
            Motor cuantitativo de predicción individual | Machine Learning & Monte Carlo
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------
# PANEL DE PARÁMETROS DE ENTRADA
# ---------------------------------------------------------------------
st.markdown('<div class="nba-card">', unsafe_allow_html=True)
st.subheader(" Configuración del Partido")

col1, col2, col3 = st.columns(3)

with col1:
    jugador = st.text_input("Jugador", value="LeBron James")
    metrica = st.selectbox("Métrica a evaluar", ["PTS", "REB", "AST", "PRA", "PR", "PA", "RA", "FG3M", "STL", "BLK"])

with col2:
    rival = st.text_input("Rival (Abreviatura)", value="GSW")
    linea = st.number_input("Línea de la apuesta", value=24.5, step=0.5)

with col3:
    local = st.checkbox("Juega de Local", value=True)
    playoffs = st.checkbox("Es Partido de Playoffs", value=False)

with st.expander(" Parámetros Avanzados (Opcionales)"):
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        spread = st.number_input("Handicap / Spread (Favorito -4.5)", value=0.0, step=0.5)
        minutos_override = st.number_input("Minutos Proyectados (0 = Automático)", value=0.0, step=1.0)
    with col_b:
        cuota_over = st.number_input("Cuota Over (Decimal)", value=1.90, step=0.05)
        cuota_under = st.number_input("Cuota Under (Decimal)", value=1.90, step=0.05)
    with col_c:
        ausentes_txt = st.text_input("Compañeros ausentes (Separados por coma)", value="")
        ausentes = [x.strip() for x in ausentes_txt.split(",") if x.strip()]

ejecutar = st.button("Ejecutar Modelo Predictivo", type="primary", use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------
# RESULTADOS DEL ANÁLISIS
# ---------------------------------------------------------------------
if ejecutar:
    if not jugador or not rival:
        st.error("Por favor completa al menos el nombre del jugador y la abreviatura del equipo rival.")
    else:
        try:
            with st.spinner(f"Analizando métricas históricas para {jugador} vs {rival}..."):
                # Carga de datos de la API / Caché
                datos = cargar_datos(jugador, ["2024-25", "2025-26"], incluir_playoffs=playoffs)
                
                # Ejecución del motor cuantitativo
                res = analizar(
                    datos=datos,
                    metrica=metrica,
                    linea=linea,
                    rival=rival.upper(),
                    local=local,
                    playoffs=playoffs,
                    companeros_fuera_hoy=ausentes,
                    minutos_override=minutos_override if minutos_override > 0 else None,
                    spread=spread if spread != 0.0 else None,
                    cuota_over=cuota_over if cuota_over > 0 else None,
                    cuota_under=cuota_under if cuota_under > 0 else None
                )

            # Contenedor de Resultados
            st.markdown('<div class="nba-card">', unsafe_allow_html=True)
            
            # Encabezado del reporte
            st.markdown(
                f"""
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                    <h3 style="margin: 0;">Reporte: {res['jugador']}</h3>
                    <span class="pill-badge pill-blue">{metrica} Línea: {linea} vs {rival}</span>
                </div>
                """,
                unsafe_allow_html=True
            )

            # Métricas Principales
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Proyección Modelo", f"{res['proyeccion_modelo']} {metrica}")
            m2.metric("Minutos Esperados", f"{res['minutos_proyectados']} min")
            m3.metric("Probabilidad Over", f"{res['probabilidad_over'] * 100:.1f}%")
            
            if "analisis_apuesta" in res:
                ap = res["analisis_apuesta"]
                m4.metric("Recomendación", ap["recomendacion"], delta=f"EV: {ap['EV'] * 100:.1f}%")

            st.divider()

            # Escenarios de Monte Carlo
            st.subheader(" Escenarios Simulados (Monte Carlo 15,000 iteraciones)")
            e1, e2 = st.columns(2)
            with e1:
                st.info(f"Piso Estadístico (Percentil 15 - Juego Duro): **{res['escenarios']['mal_juego_P15']} {metrica}**")
            with e2:
                st.success(f"Techo Estadístico (Percentil 85 - En Racha): **{res['escenarios']['techo_P85']} {metrica}**")

            # Pesos del Meta-Ensamble
            st.subheader(" Ponderación de Modelos (NNLS Meta-Ensamble)")
            st.json(res["pesos_ensamble"])

            # JSON Completo
            with st.expander(" Ver Estructura Completa de Datos (JSON)"):
                st.json(res)

            st.markdown("</div>", unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Error durante el procesamiento: {e}")
