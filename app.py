import streamlit as st
import pandas as pd
import json
from nba_api.stats.static import teams
from nba_api.stats.endpoints import commonteamroster
from nba_predictor import cargar_datos, analizar

st.set_page_config(
    page_title="NBAMetrics Pro",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------
# ESTILO VISUAL NBA
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

    .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"], .stMultiSelect div[data-baseweb="select"] {
        border-radius: 8px !important;
        background-color: #070a12 !important;
        border-color: #1e293b !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------
# BASE DE DATOS Y FUNCIONES EN CASCADA
# ---------------------------------------------------------------------
HEADERS_NBA = {
    'Host': 'stats.nba.com',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.5',
    'Referer': 'https://www.nba.com/'
}

PLANTILLAS_BASE = {
    "Los Angeles Lakers": ["LeBron James", "Anthony Davis", "Austin Reaves", "D'Angelo Russell", "Rui Hachimura", "Jarred Vanderbilt", "Gabe Vincent", "Jaxson Hayes", "Dalton Knecht", "Bronny James"],
    "Golden State Warriors": ["Stephen Curry", "Draymond Green", "Jonathan Kuminga", "Brandin Podziemski", "Andrew Wiggins", "Kevon Looney", "Buddy Hield", "Kyle Anderson", "De'Anthony Melton", "Moses Moody"],
    "Boston Celtics": ["Jayson Tatum", "Jaylen Brown", "Kristaps Porzingis", "Jrue Holiday", "Derrick White", "Al Horford", "Payton Pritchard", "Sam Hauser", "Luke Kornet"],
    "Denver Nuggets": ["Nikola Jokic", "Jamal Murray", "Aaron Gordon", "Michael Porter Jr.", "Russell Westbrook", "Christian Braun", "Peyton Watson", "DeAndre Jordan", "Dario Saric"],
    "Milwaukee Bucks": ["Giannis Antetokounmpo", "Damian Lillard", "Khris Middleton", "Brook Lopez", "Bobby Portis", "Gary Trent Jr.", "Taurean Prince", "Delon Wright"],
    "Phoenix Suns": ["Kevin Durant", "Devin Booker", "Bradley Beal", "Jusuf Nurkic", "Tyus Jones", "Grayson Allen", "Royce O'Neale", "Mason Plumlee"],
    "Dallas Mavericks": ["Luka Doncic", "Kyrie Irving", "Klay Thompson", "P.J. Washington", "Daniel Gafford", "Dereck Lively II", "Naji Marshall", "Quentin Grimes", "Spencer Dinwiddie"],
    "Minnesota Timberwolves": ["Anthony Edwards", "Julius Randle", "Donte DiVincenzo", "Rudy Gobert", "Mike Conley", "Jaden McDaniels", "Naz Reid", "Nickeil Alexander-Walker"],
    "New York Knicks": ["Jalen Brunson", "Karl-Anthony Towns", "Mikal Bridges", "OG Anunoby", "Josh Hart", "Mitchell Robinson", "Miles McBride", "Precious Achiuwa"],
    "Philadelphia 76ers": ["Joel Embiid", "Tyrese Maxey", "Paul George", "Kelly Oubre Jr.", "Caleb Martin", "Kyle Lowry", "Andre Drummond", "Eric Gordon"],
    "Miami Heat": ["Jimmy Butler", "Bam Adebayo", "Tyler Herro", "Terry Rozier", "Jaime Jaquez Jr.", "Nikola Jovic", "Duncan Robinson", "Kevin Love"],
    "Oklahoma City Thunder": ["Shai Gilgeous-Alexander", "Chet Holmgren", "Jalen Williams", "Alex Caruso", "Isaiah Hartenstein", "Luguentz Dort", "Cason Wallace", "Isaiah Joe"],
    "Indiana Pacers": ["Tyrese Haliburton", "Pascal Siakam", "Myles Turner", "Bennedict Mathurin", "Andrew Nembhard", "Aaron Nesmith", "T.J. McConnell", "Obi Toppin"],
    "Cleveland Cavaliers": ["Donovan Mitchell", "Darius Garland", "Evan Mobley", "Jarrett Allen", "Caris LeVert", "Max Strus", "Isaac Okoro", "Dean Wade"],
    "Memphis Grizzlies": ["Ja Morant", "Jaren Jackson Jr.", "Desmond Bane", "Marcus Smart", "Zach Edey", "Santi Aldama", "Brandon Clarke", "Vince Williams Jr."],
    "Sacramento Kings": ["De'Aaron Fox", "Domantas Sabonis", "DeMar DeRozan", "Keegan Murray", "Malik Monk", "Kevin Huerter", "Trey Lyles", "Keon Ellis"],
    "Orlando Magic": ["Paolo Banchero", "Franz Wagner", "Jalen Suggs", "Kentavious Caldwell-Pope", "Wendell Carter Jr.", "Cole Anthony", "Jonathan Isaac", "Moritz Wagner"],
    "Atlanta Hawks": ["Trae Young", "Jalen Johnson", "Dyson Daniels", "Clint Capela", "Bogdan Bogdanovic", "Onyeka Okongwu", "Zaccharie Risacher", "De'Andre Hunter"],
    "Chicago Bulls": ["Coby White", "Zach LaVine", "Nikola Vucevic", "Josh Giddey", "Lonzo Ball", "Patrick Williams", "Ayo Dosunmu", "Matas Buzelis"],
    "Los Angeles Clippers": ["Kawhi Leonard", "James Harden", "Ivica Zubac", "Norman Powell", "Terance Mann", "Derrick Jones Jr.", "Nicolas Batum", "Kris Dunn"],
    "Houston Rockets": ["Alperen Sengun", "Jalen Green", "Fred VanVleet", "Jabari Smith Jr.", "Dillon Brooks", "Amen Thompson", "Tari Eason", "Reed Sheppard"],
    "San Antonio Spurs": ["Victor Wembanyama", "Chris Paul", "Devin Vassell", "Stephon Castle", "Jeremy Sochan", "Keldon Johnson", "Harrison Barnes", "Tre Jones"],
    "New Orleans Pelicans": ["Zion Williamson", "Brandon Ingram", "CJ McCollum", "DeJounte Murray", "Herbert Jones", "Trey Murphy III", "Yves Missi", "Jose Alvarado"],
    "Brooklyn Nets": ["Cam Thomas", "Dennis Schroder", "Nic Claxton", "Ben Simmons", "Cam Johnson", "Dorian Finney-Smith", "Bojan Bogdanovic", "Day'Ron Sharpe"],
    "Charlotte Hornets": ["LaMelo Ball", "Brandon Miller", "Miles Bridges", "Nick Richards", "Grant Williams", "Tre Mann", "Josh Green", "Tidjane Salaun"],
    "Detroit Pistons": ["Cade Cunningham", "Jaden Ivey", "Tobias Harris", "Jalen Duren", "Malik Beasley", "Tim Hardaway Jr.", "Ausar Thompson", "Isaiah Stewart"],
    "Toronto Raptors": ["Scottie Barnes", "RJ Barrett", "Immanuel Quickley", "Jakob Poeltl", "Gradey Dick", "Kelly Olynyk", "Davion Mitchell", "Bruce Brown"],
    "Portland Trail Blazers": ["Anfernee Simons", "Jerami Grant", "Deandre Ayton", "Scoot Henderson", "Shaedon Sharpe", "Toumani Camara", "Deni Avdija", "Donovan Clingan"],
    "Utah Jazz": ["Lauri Markkanen", "Collin Sexton", "Walker Kessler", "John Collins", "Keyonte George", "Jordan Clarkson", "Taylor Hendricks", "Cody Williams"],
    "Washington Wizards": ["Kyle Kuzma", "Jordan Poole", "Jonas Valanciunas", "Alexandre Sarr", "Malcolm Brogdon", "Bub Carrington", "Corey Kispert", "Bilal Coulibaly"]
}

@st.cache_data(ttl=86400)
def obtener_diccionario_equipos():
    lista = teams.get_teams()
    lista_ordenada = sorted(lista, key=lambda x: x['full_name'])
    return {t['full_name']: {'abbrev': t['abbreviation'], 'id': t['id']} for t in lista_ordenada}

@st.cache_data(ttl=3600)
def obtener_plantilla_equipo(equipo_nombre, team_id):
    for temp in ["2026-27", "2025-26"]:
        try:
            roster = commonteamroster.CommonTeamRoster(team_id=team_id, season=temp, headers=HEADERS_NBA, timeout=8).get_data_frames()[0]
            if not roster.empty and 'PLAYER' in roster.columns:
                lista = sorted(roster['PLAYER'].unique().tolist())
                if len(lista) > 0:
                    return lista
        except Exception:
            continue
    return PLANTILLAS_BASE.get(equipo_nombre, ["LeBron James", "Anthony Davis", "Stephen Curry", "Luka Doncic", "Nikola Jokic"])

equipos_dict = obtener_diccionario_equipos()
nombres_equipos = list(equipos_dict.keys())

# ---------------------------------------------------------------------
# HEADER
# ---------------------------------------------------------------------
st.markdown(
    """
    <div class="hero-box">
        <div class="hero-title">NBAMetrics Pro</div>
        <p style="font-size: 14px; color: #94a3b8; margin-top: 6px; margin-bottom: 0;">
            Análisis cuantitativo integral y búsqueda en cascada por plantilla
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------
# PANEL DE PARÁMETROS EN CASCADA
# ---------------------------------------------------------------------
st.markdown('<div class="nba-card">', unsafe_allow_html=True)
st.subheader(" Configuración del Partido y Jugador")

col1, col2, col3 = st.columns(3)

with col1:
    idx_lakers = nombres_equipos.index("Los Angeles Lakers") if "Los Angeles Lakers" in nombres_equipos else 0
    equipo_jugador = st.selectbox("1. Equipo del Jugador", nombres_equipos, index=idx_lakers, key="sel_equipo_jugador")
    
    team_id = equipos_dict[equipo_jugador]['id']
    plantilla = obtener_plantilla_equipo(equipo_jugador, team_id)
    
    jugador = st.selectbox(
        "2. Jugador a analizar",
        options=plantilla,
        index=0,
        key=f"sel_jugador_{equipo_jugador}"
    )

with col2:
    rivales_disponibles = [eq for eq in nombres_equipos if eq != equipo_jugador]
    idx_gsw = rivales_disponibles.index("Golden State Warriors") if "Golden State Warriors" in rivales_disponibles else 0
    equipo_rival_nombre = st.selectbox("3. Equipo Rival", rivales_disponibles, index=idx_gsw, key="sel_equipo_rival")
    rival_abrev = equipos_dict[equipo_rival_nombre]['abbrev']

with col3:
    local = st.checkbox("Juega de Local", value=True)
    playoffs = st.checkbox("Es Partido de Playoffs", value=False)

companeros_disponibles = [p for p in plantilla if p != jugador]

with st.expander(" Parámetros Avanzados (Handicap, Minutos y Bajas)", expanded=True):
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        spread = st.number_input("Handicap / Spread (Favorito -4.5)", value=0.0, step=0.5)
        minutos_override = st.number_input("Minutos Proyectados (0 = Automático)", value=0.0, step=1.0)
    with col_b:
        st.write("")
    with col_c:
        ausentes = st.multiselect(
            "Compañeros ausentes hoy",
            options=companeros_disponibles,
            default=[],
            key=f"ausentes_{equipo_jugador}_{jugador}"
        )

ejecutar = st.button("Analizar Todas las Estadísticas", type="primary", use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------
# ANÁLISIS MULTIMÉTRICO COMPLETO
# ---------------------------------------------------------------------
if ejecutar:
    try:
        with st.spinner(f"Descargando datos e investigando todas las estadísticas de {jugador} vs {rival_abrev}..."):
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
                    companeros_fuera_hoy=ausentes,
                    minutos_override=minutos_override if minutos_override > 0 else None,
                    spread=spread if spread != 0.0 else None
                )
                res["nombre_largo"] = nombre_m
                resultados.append(res)

        st.markdown('<div class="nba-card">', unsafe_allow_html=True)
        
        st.markdown(
            f"""
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h3 style="margin: 0;">Reporte Integral: {jugador} ({equipos_dict[equipo_jugador]['abbrev']}) vs {equipo_rival_nombre} ({rival_abrev})</h3>
                <span class="pill-badge pill-blue">Minutos proyectados: {resultados[0]['minutos_proyectados']} min</span>
            </div>
            """,
            unsafe_allow_html=True
        )

        tabla_resumen = []
        for r in resultados:
            tabla_resumen.append({
                "Estadística": r["nombre_largo"],
                "Código": r["metrica"],
                "Proyección": r["proyeccion_modelo"],
                "Piso (P15)": r["escenarios"]["mal_juego_P15"],
                "Techo (P85)": r["escenarios"]["techo_P85"]
            })
            
        df_tabla = pd.DataFrame(tabla_resumen)
        st.dataframe(df_tabla, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader(" Desglose Detallado por Categoría")

        cols = st.columns(3)
        for idx, r in enumerate(resultados):
            with cols[idx % 3]:
                st.markdown(
                    f"""
                    <div style="background-color: #070a12; border: 1px solid #1e293b; border-radius: 10px; padding: 14px; margin-bottom: 14px;">
                        <div style="font-size: 0.85rem; color: #94a3b8; font-weight: 600;">{r['nombre_largo']} ({r['metrica']})</div>
                        <div style="font-family: 'Oswald', sans-serif; font-size: 2.2rem; font-weight: 700; color: #f8fafc; margin: 4px 0;">{r['proyeccion_modelo']}</div>
                        <div style="font-size: 0.8rem; color: #64748b;">Rango estocástico: {r['escenarios']['mal_juego_P15']} a {r['escenarios']['techo_P85']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        with st.expander(" Ver Estructura Completa de Datos de la Última Métrica (JSON)"):
            st.json(resultados[0])

        st.markdown("</div>", unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Error durante el procesamiento: {e}")
