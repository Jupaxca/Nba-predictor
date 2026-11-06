import os
import time
import json
import warnings
import unicodedata

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import nnls
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import brier_score_loss, log_loss, mean_absolute_error
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

from nba_api.stats.endpoints import leaguegamelog, playergamelog
from nba_api.stats.static import players

warnings.filterwarnings("ignore")

# --------------------------------------------------------------------------
# CONFIGURACIÓN INSTITUCIONAL
# --------------------------------------------------------------------------
SEED = 42
CACHE_DIR = "cache_nba_pro"
CACHE_HORAS = 12
PAUSA_API = 0.8
WARMUP = 12               # Juegos descartados para calentar medias móviles
MIN_JUEGOS = 50           # Mínimo histórico para inferencia
VIDA_MEDIA = 70           # Decaimiento temporal (pesa más el jugador de hoy que el de hace 2 años)
N_SPLITS = 5
N_ITER_BUSQUEDA = 20      # Búsqueda más profunda de hiperparámetros

METRICAS = {
    "PTS": ["PTS"], "REB": ["REB"], "AST": ["AST"],
    "PRA": ["PTS", "REB", "AST"], "PR": ["PTS", "REB"],
    "PA": ["PTS", "AST"], "RA": ["REB", "AST"],
    "FG3M": ["FG3M"], "STL": ["STL"], "BLK": ["BLK"],
}

# --------------------------------------------------------------------------
# UTILIDADES Y CACHÉ
# --------------------------------------------------------------------------
def _quitar_acentos(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def serie_metrica(df, metrica):
    if metrica not in METRICAS:
        raise ValueError(f"Métrica no soportada: {metrica}")
    return df[METRICAS[metrica]].sum(axis=1)

def _con_cache(nombre, funcion, reintentos=4):
    os.makedirs(CACHE_DIR, exist_ok=True)
    ruta = os.path.join(CACHE_DIR, nombre + ".pkl")
    existe = os.path.exists(ruta)
    if existe and (time.time() - os.path.getmtime(ruta)) < CACHE_HORAS * 3600:
        return pd.read_pickle(ruta)
    for i in range(reintentos):
        try:
            time.sleep(PAUSA_API)
            df = funcion()
            df.to_pickle(ruta)
            return df
        except Exception as e:
            print(f"  [API] intento {i + 1} falló ({nombre}): {e}")
            time.sleep(2 ** (i + 1))
    if existe:
        return pd.read_pickle(ruta)
    raise RuntimeError(f"Error fatal descargando {nombre}")

# --------------------------------------------------------------------------
# EXTRACCIÓN DE DATOS
# --------------------------------------------------------------------------
def _id_jugador(nombre):
    n = _quitar_acentos(nombre).lower().strip()
    lista = [p for p in players.get_players() if _quitar_acentos(p["full_name"]).lower() == n]
    if not lista:
        raise ValueError(f"Jugador no encontrado: {nombre}")
    lista.sort(key=lambda p: not p["is_active"])
    return lista[0]["id"]

def obtener_log_jugador(nombre, temporadas, incluir_playoffs=True):
    pid = _id_jugador(nombre)
    tipos = ["Regular Season"] + (["Playoffs"] if incluir_playoffs else [])
    partes = []
    for temp in temporadas:
        for tipo in tipos:
            clave = f"jug_{pid}_{temp}_{tipo.replace(' ', '')}"
            df = _con_cache(clave, lambda t=temp, ty=tipo: playergamelog.PlayerGameLog(
                player_id=pid, season=t, season_type_all_star=ty, timeout=30).get_data_frames()[0])
            if df is not None and not df.empty:
                df = df.copy()
                df["ES_PLAYOFF"] = int(tipo == "Playoffs")
                partes.append(df)
    if not partes:
        raise ValueError("Sin datos para las temporadas indicadas")
    df = pd.concat(partes, ignore_index=True)
    df = df.rename(columns={"Game_ID": "GAME_ID"})
    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
    df = df.sort_values("GAME_DATE").reset_index(drop=True)
    df["EQUIPO"] = df["MATCHUP"].str.split().str[0]
    df["RIVAL"] = df["MATCHUP"].str.split().str[-1]
    df["ES_LOCAL"] = df["MATCHUP"].str.contains("vs.", regex=False).astype(int)
    return df

def obtener_logs_equipos(temporadas, incluir_playoffs=True):
    tipos = ["Regular Season"] + (["Playoffs"] if incluir_playoffs else [])
    partes = []
    for temp in temporadas:
        for tipo in tipos:
            clave = f"equipos_{temp}_{tipo.replace(' ', '')}"
            df = _con_cache(clave, lambda t=temp, ty=tipo: leaguegamelog.LeagueGameLog(
                season=t, player_or_team_abbreviation="T", season_type_all_star=ty, timeout=30).get_data_frames()[0])
            if df is not None and not df.empty:
                partes.append(df.copy())
    eq = pd.concat(partes, ignore_index=True)
    eq["GAME_DATE"] = pd.to_datetime(eq["GAME_DATE"])
    return eq

def construir_contexto_equipos(equipos, metrica):
    t = equipos.copy()
    t["POSS"] = t["FGA"] + 0.44 * t["FTA"] - t["OREB"] + t["TOV"]
    t["M_EQ"] = serie_metrica(t, metrica)
    opp = t[["GAME_ID", "TEAM_ABBREVIATION", "PTS", "POSS", "M_EQ"]].rename(columns={
        "TEAM_ABBREVIATION": "OPP", "PTS": "PTS_OPP", "POSS": "POSS_OPP", "M_EQ": "M_PERMITIDO"})
    t = t.merge(opp, on="GAME_ID")
    t = t[t["TEAM_ABBREVIATION"] != t["OPP"]].drop_duplicates(["GAME_ID", "TEAM_ABBREVIATION"])
    t = t.sort_values(["TEAM_ABBREVIATION", "GAME_DATE"]).reset_index(drop=True)
    t["PACE_J"] = (t["POSS"] + t["POSS_OPP"]) / 2
    t["NET"] = t["PTS"] - t["PTS_OPP"]
    
    g = t.groupby("TEAM_ABBREVIATION")
    t["DIAS_DESC_EQ"] = g["GAME_DATE"].diff().dt.days
    
    for col, nom in [("M_PERMITIDO", "DEF_M"), ("PACE_J", "PACE"), ("NET", "NET_EMA"), ("PTS_OPP", "DEF_PTS")]:
        post = g[col].transform(lambda s: s.ewm(span=10, adjust=False).mean())
        post_corto = g[col].transform(lambda s: s.ewm(span=4, adjust=False).mean()) # Momento reciente defensivo
        t[nom + "_POST"] = post
        t[nom + "_PRE"] = post.groupby(t["TEAM_ABBREVIATION"]).shift(1)
        t[nom + "_REC_PRE"] = post_corto.groupby(t["TEAM_ABBREVIATION"]).shift(1)
        
    return t

def calcular_ausentes(log, companeros, temporadas, incluir_playoffs):
    aus = np.zeros(len(log))
    for nombre in companeros:
        try:
            c = obtener_log_jugador(nombre, temporadas, incluir_playoffs)
            for eq in log["EQUIPO"].unique():
                tm = c[c["EQUIPO"] == eq]
                if tm.empty: continue
                ini, fin = tm["GAME_DATE"].min(), tm["GAME_DATE"].max()
                jugados = set(tm["GAME_ID"])
                m = (log["EQUIPO"] == eq) & log["GAME_DATE"].between(ini, fin) & (~log["GAME_ID"].isin(jugados))
                aus[m.to_numpy()] += 1
        except Exception:
            continue
    return aus

# --------------------------------------------------------------------------
# INGENIERÍA DE CARACTERÍSTICAS AVANZADA
# --------------------------------------------------------------------------
def construir_features(d, metrica):
    d = d.copy().reset_index(drop=True)
    y = serie_metrica(d, metrica)
    d["Y"] = y
    
    # Manejo de fatiga en los ultimos 7 dias
    d["JUEGOS_7D"] = d.apply(lambda row: ((d["GAME_DATE"] >= row["GAME_DATE"] - pd.Timedelta(days=7)) & (d["GAME_DATE"] < row["GAME_DATE"])).sum(), axis=1)

    for span in (3, 5, 10, 20):
        d[f"EMA_{span}"] = y.ewm(span=span, adjust=False).mean().shift(1)
    
    d["VOL_5"] = y.rolling(5).std().shift(1).fillna(0)
    d["TENDENCIA"] = d["EMA_5"] - d["EMA_20"]
    
    # Proxy de Usage Rate (Impacto Ofensivo Real)
    d["USG_PROXY"] = np.where(d["MIN"] > 0, (d["FGA"] + 0.44 * d["FTA"] + d["TOV"]) / d["MIN"], 0)
    d["USG_EMA_5"] = d["USG_PROXY"].ewm(span=5, adjust=False).mean().shift(1)
    
    d["MIN_EMA_5"] = d["MIN"].ewm(span=5, adjust=False).mean().shift(1)
    d["MIN_STD_5"] = d["MIN"].rolling(5).std().shift(1).fillna(0)
    
    # Ventaja de descanso (Rest Advantage)
    d["DIAS_DESCANSO"] = d["DIAS_DESC_EQ_PROP"].fillna(3).clip(1, 7)
    d["DIAS_DESCANSO_RIV"] = d["DIAS_DESC_EQ_RIV"].fillna(3).clip(1, 7)
    d["VENTAJA_DESCANSO"] = d["DIAS_DESCANSO"] - d["DIAS_DESCANSO_RIV"]
    d["B2B"] = (d["DIAS_DESCANSO"] == 1).astype(int)

    # Contexto Rival (Largo Plazo vs Corto Plazo para detectar rachas defensivas)
    d["DEF_M_RIV"] = d["DEF_M_PRE_RIV"]
    d["DEF_M_REC_RIV"] = d["DEF_M_REC_PRE_RIV"] # Defensa reciente
    d["PACE_PARTIDO"] = (d["PACE_PRE_PROP"] + d["PACE_PRE_RIV"]) / 2
    d["DIF_FUERZA"] = d["NET_EMA_PRE_PROP"] - d["NET_EMA_PRE_RIV"]
    
    # Ajuste por blowout proyectado
    d["BLOWOUT_RISK"] = d["DIF_FUERZA"].abs().clip(lower=0, upper=20)
    
    # Rendimiento Histórico vs ESTE Rival
    yy = y.fillna(0)
    visto = y.notna().astype(int)
    suma = yy.groupby(d["RIVAL"]).cumsum() - yy
    n = visto.groupby(d["RIVAL"]).cumsum() - visto
    d["HIST_RIVAL"] = (suma + 3 * d["EMA_20"]) / (n + 3) # Shrinkage Bayesiano

    return d

def preparar_dataset(datos, metrica, prox):
    log = datos["log"].copy()
    ctx = construir_contexto_equipos(datos["equipos"], metrica)
    base = ["DIAS_DESC_EQ", "DEF_M_PRE", "DEF_M_REC_PRE", "PACE_PRE", "NET_EMA_PRE"]
    cols = ["GAME_ID", "TEAM_ABBREVIATION"] + base
    
    propio = ctx[cols].rename(columns={**{c: c + "_PROP" for c in base}, "TEAM_ABBREVIATION": "EQUIPO"})
    riv = ctx[cols].rename(columns={**{c: c + "_RIV" for c in base}, "TEAM_ABBREVIATION": "RIVAL"})
    log = log.merge(propio, on=["GAME_ID", "EQUIPO"], how="left").merge(riv, on=["GAME_ID", "RIVAL"], how="left")
    
    equipo = log["EQUIPO"].iloc[-1]
    rival = prox["rival"]
    rp = ctx[ctx["TEAM_ABBREVIATION"] == equipo].sort_values("GAME_DATE").iloc[-1]
    rr = ctx[ctx["TEAM_ABBREVIATION"] == rival].sort_values("GAME_DATE").iloc[-1]
    fecha = pd.Timestamp(prox["fecha"]) if prox["fecha"] else rp["GAME_DATE"] + pd.Timedelta(days=2)
    
    nueva = {c: np.nan for c in log.columns}
    nueva.update(
        GAME_ID="PROX", GAME_DATE=fecha, EQUIPO=equipo, RIVAL=rival,
        MATCHUP=f"{equipo} {'vs.' if prox['local'] else '@'} {rival}",
        ES_LOCAL=int(prox["local"]), ES_PLAYOFF=int(prox["playoffs"]),
        DIAS_DESC_EQ_PROP=(fecha - rp["GAME_DATE"]).days,
        DIAS_DESC_EQ_RIV=(fecha - rr["GAME_DATE"]).days,
        DEF_M_PRE_RIV=rr["DEF_M_POST"], DEF_M_REC_PRE_RIV=rr["DEF_M_REC_POST"],
        PACE_PRE_PROP=rp["PACE_POST"], PACE_PRE_RIV=rr["PACE_POST"],
        NET_EMA_PRE_PROP=rp["NET_EMA_POST"], NET_EMA_PRE_RIV=rr["NET_EMA_POST"],
        N_AUSENTES=float(len(prox["fuera_hoy"]))
    )
    
    log = pd.concat([log, pd.DataFrame([nueva])], ignore_index=True)
    d = construir_features(log, metrica)
    
    if prox["spread"] is not None: 
        d.loc[d.index[-1], "DIF_FUERZA"] = float(prox["spread"])
        d.loc[d.index[-1], "BLOWOUT_RISK"] = abs(float(prox["spread"]))
        
    return d

# --------------------------------------------------------------------------
# META-ENSAMBLE DE MODELOS Y MATEMÁTICAS DE APUESTAS
# --------------------------------------------------------------------------
def buscar_hiperparametros(X, y, w, rng, metrica_tipo):
    # Asigna la funcion de perdida segun la metrica (Poisson para conteos es ORO)
    obj = "count:poisson" if metrica_tipo in ["AST", "REB", "STL", "BLK"] else "reg:tweedie"
    
    mejor, mejor_mae = None, np.inf
    for _ in range(N_ITER_BUSQUEDA):
        p = dict(
            n_estimators=int(rng.choice([150, 250, 350])),
            learning_rate=float(rng.choice([0.015, 0.03, 0.05])),
            max_depth=int(rng.choice([2, 3, 4])),
            subsample=float(rng.choice([0.7, 0.85, 0.95])),
            colsample_bytree=float(rng.choice([0.6, 0.8, 1.0])),
            reg_lambda=float(rng.choice([1, 5, 10])),
            objective=obj
        )
        oof = np.full(len(y), np.nan)
        for tr, te in TimeSeriesSplit(n_splits=3).split(X):
            m = XGBRegressor(**p, random_state=SEED, n_jobs=1, verbosity=0)
            m.fit(X.iloc[tr], y.iloc[tr], sample_weight=w[tr])
            oof[te] = m.predict(X.iloc[te])
        
        m_idx = ~np.isnan(oof)
        mae = mean_absolute_error(y[m_idx], oof[m_idx])
        if mae < mejor_mae:
            mejor, mejor_mae = p, mae
    return mejor

def evaluar_apuesta(prob_over, cuota_over, cuota_under, n_oof, min_ev=0.03):
    p_imp_o = 1 / cuota_over
    p_imp_u = 1 / cuota_under if cuota_under else p_imp_o / 1.045 # Asume vig de 4.5% si no hay under
    p_mkt_over = p_imp_o / (p_imp_o + p_imp_u)
    
    # Kelly fraccionado adaptativo
    w = min(n_oof / (n_oof + 80), 0.85) # Confianza máxima del modelo = 85% vs Mercado
    p_over = w * prob_over + (1 - w) * p_mkt_over
    p_under = 1 - p_over
    
    res = {}
    for lado, p, c in [("OVER", p_over, cuota_over), ("UNDER", p_under, cuota_under)]:
        if not c: continue
        ev = (p * (c - 1)) - (1 - p)
        kelly = max(0.0, ev / (c - 1)) * 0.25 # Cuarto de Kelly (Control de riesgo estricto)
        res[lado] = {"prob": round(p, 4), "ev": round(ev, 4), "kelly_recomendado": round(min(kelly, 0.05), 4)}
        
    mejor = max(res, key=lambda k: res[k]["ev"])
    return {
        "lado": mejor,
        "EV": res[mejor]["ev"],
        "kelly": res[mejor]["kelly_recomendado"],
        "recomendacion": "APOSTAR" if res[mejor]["ev"] >= min_ev else "PASAR"
    }

def analizar(datos, metrica, linea, rival, local=True, fecha_juego=None, playoffs=False,
             companeros_fuera_hoy=None, minutos_override=None, spread=None, cuota_over=None, cuota_under=None):
    
    rng = np.random.default_rng(SEED)
    prox = {"rival": rival, "local": local, "fecha": fecha_juego, "playoffs": playoffs,
            "fuera_hoy": companeros_fuera_hoy or [], "spread": spread}
    
    d = preparar_dataset(datos, metrica, prox)
    fit_df = d[d["Y"].notna()].iloc[WARMUP:]
    
    features = [
        "EMA_5", "EMA_10", "EMA_20", "VOL_5", "TENDENCIA", 
        "MIN_EMA_5", "MIN_STD_5", "USG_EMA_5", 
        "VENTAJA_DESCANSO", "JUEGOS_7D", "N_AUSENTES",
        "DEF_M_RIV", "DEF_M_REC_RIV", "PACE_PARTIDO", "BLOWOUT_RISK", "HIST_RIVAL"
    ]
    
    x_next = d.iloc[[-1]][features]
    X = fit_df[features].reset_index(drop=True)
    y = fit_df["Y"].reset_index(drop=True)
    ym = fit_df["MIN"].reset_index(drop=True)
    n = len(y)
    
    # Context Weighting: Da más peso a juegos pasados donde faltaron la misma cantidad de compañeros
    peso_base = 0.5 ** ((n - 1 - np.arange(n)) / VIDA_MEDIA)
    if len(prox["fuera_hoy"]) > 0:
        similitud_contexto = (fit_df["N_AUSENTES"] == len(prox["fuera_hoy"])).to_numpy()
        w = peso_base * np.where(similitud_contexto, 1.5, 1.0) # Multiplicador de contexto
    else:
        w = peso_base

    # ETAPA 1: Predicción de Minutos
    m_min = HistGradientBoostingRegressor(loss="squared_error", max_depth=4, learning_rate=0.03, random_state=SEED)
    m_min.fit(X, ym, sample_weight=w)
    min_pred = float(minutos_override) if minutos_override else float(m_min.predict(x_next)[0])
    
    X2 = X.copy()
    X2["MIN_PRED"] = m_min.predict(X)
    x2_next = x_next.copy()
    x2_next["MIN_PRED"] = min_pred

    # ETAPA 2: Meta-Ensamble
    # 1. XGBoost Específico (Poisson o Tweedie)
    params = buscar_hiperparametros(X2, y, w, rng, metrica)
    m_xgb = XGBRegressor(**params, random_state=SEED, n_jobs=1, verbosity=0).fit(X2, y, sample_weight=w)
    # 2. HistGradientBoosting (LigthGBM Proxy)
    m_hgb = HistGradientBoostingRegressor(loss="poisson" if metrica in ["AST","REB","STL","BLK"] else "squared_error", 
                                          max_depth=3, random_state=SEED).fit(X2, y, sample_weight=w)
    # 3. Baseline Lineal
    m_ridge = Ridge(alpha=20.0).fit(SimpleImputer(strategy="median").fit_transform(X2), y)

    preds_xgb = m_xgb.predict(X2)
    preds_hgb = m_hgb.predict(X2)
    preds_lin = m_ridge.predict(SimpleImputer(strategy="median").fit_transform(X2))
    
    # NNLS (Non-Negative Least Squares) para descubrir quién proyecta mejor históricamente
    A = np.column_stack([preds_xgb, preds_hgb, preds_lin])
    pesos, _ = nnls(A, y.to_numpy())
    pesos = pesos / pesos.sum() if pesos.sum() > 0 else np.array([0.4, 0.4, 0.2])
    
    # Proyección final
    nx_imp = SimpleImputer(strategy="median").fit(X2).transform(x2_next)
    mu = float(np.clip(pesos @ np.array([m_xgb.predict(x2_next)[0], m_hgb.predict(x2_next)[0], m_ridge.predict(nx_imp)[0]]), 0, None))

    # ETAPA 3: Simulación Monte Carlo y Probabilidad
    oof_ens = A @ pesos
    residuos = y.to_numpy() - oof_ens
    var_residuos = np.maximum(residuos**2, mu * 1.05) # Varianza mínima
    
    # Bootstrap Simulación
    sim = np.maximum(0, np.round(mu + rng.choice(residuos, size=15000, replace=True)))
    p_boot = float(np.mean(sim > linea))
    
    resultado = {
        "jugador": datos["nombre"], "metrica": metrica, "linea": linea,
        "proyeccion_modelo": round(mu, 2),
        "minutos_proyectados": round(min_pred, 1),
        "probabilidad_over": round(p_boot, 4),
        "pesos_ensamble": dict(zip(["XGBoost", "HistGBM", "Lineal"], np.round(pesos, 2))),
        "escenarios": {"mal_juego_P15": float(np.percentile(sim, 15)), "techo_P85": float(np.percentile(sim, 85))}
    }
    
    if cuota_over:
        resultado["analisis_apuesta"] = evaluar_apuesta(p_boot, cuota_over, cuota_under, len(y))
        
    return resultado

# --------------------------------------------------------------------------
# EJECUCIÓN DEL SCRIPT
# --------------------------------------------------------------------------
if __name__ == "__main__":
    datos = cargar_datos("LeBron James", ["2024-25", "2025-26"], companeros_clave=["Anthony Davis"])
    
    res = analizar(
        datos=datos, metrica="PRA", linea=38.5, rival="GSW", local=True,
        fecha_juego="2026-11-06", # Toma en cuenta fatiga exacta a la fecha
        companeros_fuera_hoy=[],  # Agrega "Anthony Davis" si se lesiona para ver el impacto en usage
        spread=-4.5,              # Lakers favoritos por 4.5
        cuota_over=1.90, cuota_under=1.90
    )
    
    print("\n--- REPORTE PROFESIONAL ---")
    print(json.dumps(res, indent=4, ensure_ascii=False))
