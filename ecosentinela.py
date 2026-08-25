"""
EcoSentinela — o "Waze do meio ambiente"
Protótipo funcional em Streamlit.

A comunidade reporta e valida problemas ambientais locais, que podem virar
protocolos oficiais acompanháveis junto à Secretaria de Meio Ambiente.

Como rodar:
    pip install -r requirements.txt
    streamlit run app.py
"""

from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timedelta

import folium
import pandas as pd
import plotly.express as px
import streamlit as st
from folium.plugins import HeatMap
from streamlit_folium import st_folium

# =============================================================================
# CONFIGURAÇÃO GERAL DA PÁGINA
# =============================================================================

st.set_page_config(
    page_title="EcoSentinela",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Cidade-base do protótipo (pode ser trocada por qualquer município)
CIDADE_NOME = "Santarém, PA"
CIDADE_LAT = -2.4383
CIDADE_LON = -54.6892

CATEGORIAS = {
    "Lixo": {"emoji": "🗑️", "cor": "#c8922f"},
    "Desmate": {"emoji": "🌳", "cor": "#3b5d45"},
    "Água": {"emoji": "💧", "cor": "#2f6690"},
}

ESTAGIOS = ["Reportado", "Validado", "Secretaria", "Em campo", "Resolvido"]
LIMIAR_CONFIRMACOES = 30
EQUIPES = ["Fiscalização Ambiental · Zona Norte", "Fiscalização Ambiental · Zona Sul",
           "Fiscalização Ambiental · Zona Leste", "Recursos Hídricos", "Manejo de Resíduos"]

# =============================================================================
# TEMA (DARK / LIGHT) — cores inspiradas na identidade visual do EcoSentinela
# =============================================================================

THEMES = {
    "dark": {
        "bg": "#1e2f25",
        "bg_secondary": "#26392c",
        "card": "#2c4030",
        "text": "#f2efe6",
        "text_muted": "#c7d3c6",
        "accent": "#caa053",
        "accent_2": "#4a7a5c",
        "blue": "#5a92b8",
        "border": "#3d5644",
        "plot_bg": "#26392c",
    },
    "light": {
        "bg": "#f7f4ee",
        "bg_secondary": "#ffffff",
        "card": "#ffffff",
        "text": "#243a2c",
        "text_muted": "#5b6f60",
        "accent": "#b8791f",
        "accent_2": "#3b5d45",
        "blue": "#2f6690",
        "border": "#e1ddd0",
        "plot_bg": "#ffffff",
    },
}


def inject_theme_css(mode: str) -> None:
    t = THEMES[mode]
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-color: {t['bg']};
            color: {t['text']};
        }}
        section[data-testid="stSidebar"] {{
            background-color: {t['bg_secondary']};
            border-right: 1px solid {t['border']};
        }}
        h1, h2, h3, h4, h5, h6, p, span, label, li {{
            color: {t['text']} !important;
        }}
        .es-muted {{ color: {t['text_muted']} !important; font-size: 0.9rem; }}
        .es-card {{
            background-color: {t['card']};
            border: 1px solid {t['border']};
            border-radius: 12px;
            padding: 1rem 1.2rem;
            margin-bottom: 0.8rem;
        }}
        .es-badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 999px;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }}
        .es-badge-live {{ background-color: {t['accent']}; color: #241a08; }}
        .es-badge-blue {{ background-color: {t['blue']}; color: #0c1b25; }}
        .es-badge-green {{ background-color: {t['accent_2']}; color: #eaf3ea; }}
        .es-step {{
            flex: 1;
            text-align: center;
            padding: 6px 4px;
            border-radius: 8px;
            font-size: 0.72rem;
            font-weight: 700;
        }}
        .es-step-done {{ background-color: {t['accent_2']}; color: #eaf3ea; }}
        .es-step-current {{ background-color: {t['accent']}; color: #241a08; }}
        .es-step-todo {{ background-color: {t['border']}; color: {t['text_muted']}; }}
        div[data-testid="stMetric"] {{
            background-color: {t['card']};
            border: 1px solid {t['border']};
            border-radius: 12px;
            padding: 0.8rem 1rem;
        }}
        .stButton>button {{
            border-radius: 8px;
            font-weight: 600;
        }}
        .stButton>button[kind="primary"] {{
            background-color: {t['accent']};
            border: none;
            color: #241a08;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# =============================================================================
# DADOS (estado em memória, simulando o backend do app)
# =============================================================================

def _jitter(lat: float, lon: float, spread: float = 0.05) -> tuple[float, float]:
    return lat + random.uniform(-spread, spread), lon + random.uniform(-spread, spread)


def _gerar_report_demo(i: int) -> dict:
    categoria = random.choice(list(CATEGORIAS.keys()))
    lat, lon = _jitter(CIDADE_LAT, CIDADE_LON)
    estagio_idx = random.choices(range(5), weights=[10, 25, 20, 25, 20])[0]
    confirmacoes = random.randint(0, 45) if estagio_idx > 0 else random.randint(0, 12)
    tem_protocolo = estagio_idx >= 2
    criado = datetime.now() - timedelta(days=random.randint(0, 40))
    return {
        "id": str(uuid.uuid4())[:8],
        "titulo": f"{CATEGORIAS[categoria]['emoji']} {categoria} — relato #{i}",
        "categoria": categoria,
        "descricao": random.choice([
            "Acúmulo de lixo em terreno baldio próximo à via principal.",
            "Área com sinais de desmatamento recente às margens do igarapé.",
            "Água com aspecto turvo e odor forte reportado por moradores.",
            "Descarte irregular de entulho em ponto sem coleta.",
            "Mata ciliar comprometida após queimada não autorizada.",
        ]),
        "lat": lat,
        "lon": lon,
        "anonimo": random.random() < 0.25,
        "criado_em": criado,
        "status": ESTAGIOS[estagio_idx],
        "confirmacoes": confirmacoes,
        "protocolo": f"SMA-{2000 + i}" if tem_protocolo else None,
        "equipe": random.choice(EQUIPES) if estagio_idx >= 3 else None,
        "prazo_dias": random.choice([3, 5, 7, 10]) if estagio_idx >= 2 else None,
        "autor": random.choice(["voce", "outro"]) if i > 3 else "voce",
    }


def init_state() -> None:
    if "theme" not in st.session_state:
        st.session_state.theme = "dark"
    if "reports" not in st.session_state:
        random.seed(42)
        st.session_state.reports = [_gerar_report_demo(i) for i in range(1, 19)]
    if "pagina" not in st.session_state:
        st.session_state.pagina = "Mapa"
    if "detalhe_id" not in st.session_state:
        st.session_state.detalhe_id = st.session_state.reports[0]["id"]
    if "geo_detectado" not in st.session_state:
        st.session_state.geo_detectado = _jitter(CIDADE_LAT, CIDADE_LON, 0.02)


def reports_df() -> pd.DataFrame:
    return pd.DataFrame(st.session_state.reports)


def get_report(report_id: str) -> dict | None:
    for r in st.session_state.reports:
        if r["id"] == report_id:
            return r
    return None


def talvez_gerar_protocolo(report: dict) -> None:
    """Encaminha automaticamente à Secretaria quando atinge o limiar de confirmações."""
    if report["protocolo"] is None and report["confirmacoes"] >= LIMIAR_CONFIRMACOES:
        numero = 2000 + random.randint(1, 999)
        report["protocolo"] = f"SMA-{numero}"
        report["status"] = "Secretaria"
        report["equipe"] = random.choice(EQUIPES)
        report["prazo_dias"] = random.choice([3, 5, 7])
    elif report["protocolo"] is None and report["status"] == "Reportado" and report["confirmacoes"] >= 5:
        report["status"] = "Validado"


# =============================================================================
# TELA 01 · MAPA
# =============================================================================

def tela_mapa() -> None:
    t = THEMES[st.session_state.theme]
    st.markdown("### 🗺️ Mapa principal")
    st.caption("Tiles OpenStreetMap + camada de reports em tempo real")

    df = reports_df()
    camada = st.radio(
        "Camada",
        ["📍 Pins", "🔥 Calor", "🏛️ Oficial"],
        horizontal=True,
        label_visibility="collapsed",
    )

    col_map, col_info = st.columns([2.4, 1])

    with col_map:
        m = folium.Map(
            location=[CIDADE_LAT, CIDADE_LON],
            zoom_start=12,
            tiles="CartoDB dark_matter" if st.session_state.theme == "dark" else "CartoDB positron",
        )

        if camada == "🔥 Calor":
            HeatMap(df[["lat", "lon"]].values.tolist(), radius=22, blur=18).add_to(m)
        elif camada == "🏛️ Oficial":
            # Zonas oficiais simuladas (unidades de conservação / zonas de fiscalização)
            zonas = [
                {"nome": "Zona de Fiscalização Norte", "lat": CIDADE_LAT + 0.03, "lon": CIDADE_LON - 0.02},
                {"nome": "Unidade de Conservação Ribeirinha", "lat": CIDADE_LAT - 0.025, "lon": CIDADE_LON + 0.03},
            ]
            for z in zonas:
                folium.Rectangle(
                    bounds=[[z["lat"] - 0.012, z["lon"] - 0.015], [z["lat"] + 0.012, z["lon"] + 0.015]],
                    color=t["blue"],
                    weight=2,
                    dash_array="6,6",
                    fill=True,
                    fill_opacity=0.12,
                    popup=z["nome"],
                ).add_to(m)
            for _, row in df.iterrows():
                folium.CircleMarker(
                    location=[row["lat"], row["lon"]],
                    radius=6,
                    color=CATEGORIAS[row["categoria"]]["cor"],
                    fill=True,
                    fill_opacity=0.9,
                    popup=row["titulo"],
                ).add_to(m)
        else:
            for _, row in df.iterrows():
                oficial = row["protocolo"] is not None
                folium.CircleMarker(
                    location=[row["lat"], row["lon"]],
                    radius=7,
                    color=CATEGORIAS[row["categoria"]]["cor"],
                    weight=3 if oficial else 1,
                    dash_array="4,4" if oficial else None,
                    fill=True,
                    fill_color=CATEGORIAS[row["categoria"]]["cor"],
                    fill_opacity=0.9,
                    popup=folium.Popup(
                        f"<b>{row['titulo']}</b><br>Status: {row['status']}<br>"
                        f"{'Protocolo ' + row['protocolo'] if oficial else 'Sem protocolo ainda'}",
                        max_width=220,
                    ),
                ).add_to(m)

        st_folium(m, use_container_width=True, height=460, key="mapa_principal")

    with col_info:
        total = len(df)
        com_protocolo = int((df["protocolo"].notna()).sum())
        st.markdown(
            f"""
            <div class="es-card">
                <div style="font-size:1.6rem; font-weight:800;">{total} problemas ativos</div>
                <div class="es-muted">{com_protocolo} já com protocolo aberto na prefeitura</div>
                <br><span class="es-badge es-badge-live">● AO VIVO</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("**Legenda de categorias**")
        for cat, info in CATEGORIAS.items():
            st.markdown(
                f'<span style="color:{info["cor"]}; font-weight:700;">●</span> {info["emoji"]} {cat}',
                unsafe_allow_html=True,
            )
        st.markdown(
            '<p class="es-muted">Contorno tracejado = área já com protocolo oficial em andamento.</p>',
            unsafe_allow_html=True,
        )


# =============================================================================
# TELA 02 · REPORTAR
# =============================================================================

def tela_reportar() -> None:
    st.markdown("### 📸 Novo report")
    st.caption("POST /reports {foto, categoria, geo, texto, anônimo}")

    col1, col2 = st.columns([1, 1.2])

    with col1:
        foto = st.camera_input("Toque para fotografar")
        if foto is not None:
            st.markdown(
                '<span class="es-badge es-badge-green">📍 Geolocalização e timestamp embutidos</span>',
                unsafe_allow_html=True,
            )

    with col2:
        categoria = st.radio(
            "Categoria",
            list(CATEGORIAS.keys()),
            format_func=lambda c: f"{CATEGORIAS[c]['emoji']} {c}",
            horizontal=True,
        )

        st.markdown("**📍 Local detectado**")
        c_lat, c_lon, c_btn = st.columns([1, 1, 0.8])
        lat_atual, lon_atual = st.session_state.geo_detectado
        with c_lat:
            lat_in = st.number_input("Latitude", value=float(lat_atual), format="%.5f")
        with c_lon:
            lon_in = st.number_input("Longitude", value=float(lon_atual), format="%.5f")
        with c_btn:
            st.write("")
            st.write("")
            if st.button("🔄 Detectar"):
                st.session_state.geo_detectado = _jitter(CIDADE_LAT, CIDADE_LON, 0.02)
                st.rerun()

        texto = st.text_area("Descreva em poucas palavras", placeholder="Ex.: lixo acumulado na esquina há dias…")
        anonimo = st.checkbox("🙈 Denúncia anônima", help="Protege o denunciante em casos sensíveis.")

        enviar = st.button("ENVIAR REPORT", type="primary", use_container_width=True)

        if enviar:
            if not texto.strip():
                st.warning("Descreva o problema antes de enviar.")
            else:
                novo = {
                    "id": str(uuid.uuid4())[:8],
                    "titulo": f"{CATEGORIAS[categoria]['emoji']} {categoria} — {texto[:28]}",
                    "categoria": categoria,
                    "descricao": texto.strip(),
                    "lat": lat_in,
                    "lon": lon_in,
                    "anonimo": anonimo,
                    "criado_em": datetime.now(),
                    "status": "Reportado",
                    "confirmacoes": 0,
                    "protocolo": None,
                    "equipe": None,
                    "prazo_dias": None,
                    "autor": "voce",
                }
                st.session_state.reports.insert(0, novo)
                st.session_state.detalhe_id = novo["id"]
                st.success("Report enviado! Iniciando checagem de duplicatas antes de publicar.")
                st.balloons()


# =============================================================================
# TELA 03 + 04 · DETALHE / PROTOCOLO
# =============================================================================

def render_stepper(status: str) -> None:
    idx_atual = ESTAGIOS.index(status)
    cols = st.columns(len(ESTAGIOS))
    for i, (col, nome) in enumerate(zip(cols, ESTAGIOS)):
        if i < idx_atual:
            css = "es-step-done"
        elif i == idx_atual:
            css = "es-step-current"
        else:
            css = "es-step-todo"
        col.markdown(f'<div class="es-step {css}">{nome}</div>', unsafe_allow_html=True)


def tela_detalhe() -> None:
    st.markdown("### 🔎 Detalhe do report")
    st.caption("GET /reports/{id}")

    df = reports_df()
    opcoes = {f"{r['titulo']}  ·  {r['id']}": r["id"] for r in st.session_state.reports}
    escolha = st.selectbox("Selecione um report", list(opcoes.keys()))
    report_id = opcoes[escolha]
    st.session_state.detalhe_id = report_id
    r = get_report(report_id)
    if r is None:
        st.info("Nenhum report encontrado.")
        return

    render_stepper(r["status"])
    st.write("")

    col1, col2 = st.columns([1.3, 1])

    with col1:
        st.markdown(
            f"""
            <div class="es-card">
                <h4>{r['titulo']}</h4>
                <p class="es-muted">{r['descricao']}</p>
                <p class="es-muted">📅 {r['criado_em'].strftime('%d/%m/%Y')} ·
                {'🙈 Denúncia anônima' if r['anonimo'] else '🙋 Identificado'}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(f"**👀 {r['confirmacoes']} confirmações**")
        st.progress(min(r["confirmacoes"] / LIMIAR_CONFIRMACOES, 1.0))
        st.caption(f"Limiar para encaminhamento automático: {LIMIAR_CONFIRMACOES} confirmações")
        if st.button("✅ Toque para confirmar que você também viu"):
            r["confirmacoes"] += 1
            talvez_gerar_protocolo(r)
            st.rerun()

    with col2:
        if r["protocolo"]:
            st.markdown(
                f"""
                <div class="es-card">
                    <span class="es-badge es-badge-blue">EM ANÁLISE</span>
                    <h4>🏛️ Protocolo {r['protocolo']}</h4>
                    <p class="es-muted">Secretaria Municipal de Meio Ambiente</p>
                    <p class="es-muted">Recebido automaticamente via API</p>
                    <hr style="border-color:rgba(128,128,128,0.2)">
                    <p><b>Equipe designada</b><br>{r['equipe'] or '—'}</p>
                    <p><b>Prazo estimado</b><br>Vistoria em até {r['prazo_dias'] or '–'} dias úteis</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            oficio = (
                f"OFÍCIO Nº {r['protocolo']}\n"
                f"Secretaria Municipal de Meio Ambiente\n\n"
                f"Assunto: {r['titulo']}\n"
                f"Descrição: {r['descricao']}\n"
                f"Localização: {r['lat']:.5f}, {r['lon']:.5f}\n"
                f"Equipe designada: {r['equipe']}\n"
                f"Prazo estimado: {r['prazo_dias']} dias úteis\n"
                f"Status atual: {r['status']}\n"
                f"Confirmações da comunidade: {r['confirmacoes']}\n"
                f"Gerado automaticamente pelo EcoSentinela em {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
            )
            st.download_button("📄 Ver ofício oficial", oficio, file_name=f"oficio_{r['protocolo']}.txt")

            if r["status"] != "Resolvido":
                novo_idx = min(ESTAGIOS.index(r["status"]) + 1, len(ESTAGIOS) - 1)
                if st.button("➡️ Simular avanço de status (equipe em campo)"):
                    r["status"] = ESTAGIOS[novo_idx]
                    st.rerun()
        else:
            st.markdown(
                """
                <div class="es-card">
                    <p class="es-muted">Este report ainda não atingiu o limiar de confirmações
                    da comunidade e por isso ainda não foi encaminhado à Secretaria.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )


# =============================================================================
# TELA 05 · PAINEL DA SECRETARIA
# =============================================================================

def tela_painel_secretaria() -> None:
    t = THEMES[st.session_state.theme]
    st.markdown("### 🏛️ Painel EcoSentinela · Secretaria Municipal de Meio Ambiente")
    st.caption("GET /admin/reports · webview interna")

    df = reports_df()
    este_mes = df[df["criado_em"] >= datetime.now() - timedelta(days=30)]
    protocolos_abertos = df[(df["protocolo"].notna()) & (df["status"] != "Resolvido")]
    resolvidos = df[df["status"] == "Resolvido"]
    pct_10dias = 0
    if len(protocolos_abertos) + len(resolvidos) > 0:
        pct_10dias = int(64)  # valor de referência ilustrativo, conforme protótipo

    c1, c2, c3 = st.columns(3)
    c1.metric("Reports este mês", len(este_mes))
    c2.metric("Protocolos abertos", len(protocolos_abertos))
    c3.metric("Resolvidos em 10 dias", f"{pct_10dias}%")

    aba_mapa, aba_protocolos, aba_relatorios = st.tabs(["📍 Mapa de calor", "📋 Protocolos", "📈 Relatórios"])

    with aba_mapa:
        m = folium.Map(
            location=[CIDADE_LAT, CIDADE_LON],
            zoom_start=12,
            tiles="CartoDB dark_matter" if st.session_state.theme == "dark" else "CartoDB positron",
        )
        HeatMap(df[["lat", "lon"]].values.tolist(), radius=22, blur=18).add_to(m)
        st_folium(m, use_container_width=True, height=400, key="mapa_secretaria")

    with aba_protocolos:
        st.markdown("**Atribuir equipe e atualizar status**")
        editable = df[["id", "titulo", "categoria", "status", "protocolo", "equipe", "confirmacoes"]].copy()
        edited = st.data_editor(
            editable,
            column_config={
                "status": st.column_config.SelectboxColumn("status", options=ESTAGIOS),
                "equipe": st.column_config.SelectboxColumn("equipe", options=[None] + EQUIPES),
            },
            disabled=["id", "titulo", "categoria", "protocolo", "confirmacoes"],
            use_container_width=True,
            hide_index=True,
            key="editor_protocolos",
        )
        if st.button("💾 Salvar alterações"):
            for _, row in edited.iterrows():
                r = get_report(row["id"])
                if r:
                    r["status"] = row["status"]
                    r["equipe"] = row["equipe"]
            st.success("Status atualizados. O cidadão verá a mudança refletida em tempo real.")

        geo = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
                    "properties": {
                        "id": r["id"],
                        "titulo": r["titulo"],
                        "categoria": r["categoria"],
                        "status": r["status"],
                        "protocolo": r["protocolo"],
                        "confirmacoes": r["confirmacoes"],
                    },
                }
                for r in st.session_state.reports
            ],
        }
        st.download_button(
            "⚙️ EXPORTAR .GEOJSON",
            data=json.dumps(geo, ensure_ascii=False, indent=2, default=str),
            file_name="ecosentinela_reports.geojson",
            mime="application/geo+json",
        )

    with aba_relatorios:
        col1, col2 = st.columns(2)
        with col1:
            contagem_cat = df["categoria"].value_counts().reset_index()
            contagem_cat.columns = ["categoria", "quantidade"]
            fig = px.bar(
                contagem_cat, x="categoria", y="quantidade", color="categoria",
                color_discrete_map={k: v["cor"] for k, v in CATEGORIAS.items()},
                title="Reports por categoria",
            )
            fig.update_layout(
                plot_bgcolor=t["plot_bg"], paper_bgcolor=t["plot_bg"], font_color=t["text"],
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            contagem_status = df["status"].value_counts().reindex(ESTAGIOS).fillna(0).reset_index()
            contagem_status.columns = ["status", "quantidade"]
            fig2 = px.pie(contagem_status, names="status", values="quantidade", title="Distribuição por estágio")
            fig2.update_layout(plot_bgcolor=t["plot_bg"], paper_bgcolor=t["plot_bg"], font_color=t["text"])
            st.plotly_chart(fig2, use_container_width=True)


# =============================================================================
# TELA 06 · FEED & PERFIL
# =============================================================================

def tela_perfil() -> None:
    st.markdown("### 🏅 Meu impacto")
    df = reports_df()
    meus = df[df["autor"] == "voce"]
    protocolos = meus[meus["protocolo"].notna()]
    resolvidos = meus[meus["status"] == "Resolvido"]

    col1, col2 = st.columns([1, 1.3])
    with col1:
        st.markdown(
            f"""
            <div class="es-card">
                <div style="font-size:1.5rem; font-weight:800;">{len(meus)} reports · {len(protocolos)} protocolos</div>
                <div class="es-muted">{len(resolvidos)} problemas já resolvidos</div>
            </div>
            <div class="es-card">
                <span class="es-badge es-badge-live">SELO NOVO</span>
                <h4>🥇 Guardião do bairro</h4>
                <p class="es-muted">Top 3 no ranking local</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if len(protocolos) > 0:
            st.markdown(
                """
                <div class="es-card">
                    <span class="es-badge es-badge-blue">IMPACTO REAL</span>
                    <h4>🏛️ Vistoria confirmada</h4>
                    <p class="es-muted">Seu report virou fiscalização real.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with col2:
        st.markdown("**📰 Feed do bairro**")
        recentes = df.sort_values("criado_em", ascending=False).head(8)
        for _, r in recentes.iterrows():
            icone = CATEGORIAS[r["categoria"]]["emoji"]
            linha = f"{icone} **{r['titulo']}** — status atual: *{r['status']}*"
            if r["protocolo"]:
                linha += f" (protocolo {r['protocolo']})"
            st.markdown(f'<div class="es-card">{linha}<br>'
                        f'<span class="es-muted">{r["criado_em"].strftime("%d/%m/%Y")}</span></div>',
                        unsafe_allow_html=True)


# =============================================================================
# SIDEBAR / NAVEGAÇÃO
# =============================================================================

def sidebar() -> None:
    with st.sidebar:
        st.markdown("## 🛰️ EcoSentinela")
        st.caption("Edição expandida · Disciplina de Ciências Ambientais")

        modo = st.toggle("🌙 Modo escuro", value=(st.session_state.theme == "dark"))
        novo_tema = "dark" if modo else "light"
        if novo_tema != st.session_state.theme:
            st.session_state.theme = novo_tema
            st.rerun()

        st.divider()
        st.session_state.pagina = st.radio(
            "Navegação",
            [
                "Mapa",
                "Reportar",
                "Detalhe / Protocolo",
                "Painel da Secretaria",
                "Feed & Perfil",
            ],
            index=[
                "Mapa", "Reportar", "Detalhe / Protocolo", "Painel da Secretaria", "Feed & Perfil"
            ].index(st.session_state.pagina) if st.session_state.pagina in [
                "Mapa", "Reportar", "Detalhe / Protocolo", "Painel da Secretaria", "Feed & Perfil"
            ] else 0,
        )
        st.divider()
        st.markdown(
            '<p class="es-muted">Do report do cidadão ao protocolo oficial — '
            'conectando comunidade e poder público em torno do meio ambiente local.</p>',
            unsafe_allow_html=True,
        )
        st.markdown(f'<p class="es-muted">📍 Base: {CIDADE_NOME}</p>', unsafe_allow_html=True)


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    init_state()
    inject_theme_css(st.session_state.theme)
    sidebar()

    st.title("EcoSentinela")
    st.caption('O "Waze do meio ambiente": a comunidade reporta e valida problemas ambientais '
               "locais — com ponte direta para a Secretaria de Meio Ambiente agir sobre eles.")
    st.write("")

    pagina = st.session_state.pagina
    if pagina == "Mapa":
        tela_mapa()
    elif pagina == "Reportar":
        tela_reportar()
    elif pagina == "Detalhe / Protocolo":
        tela_detalhe()
    elif pagina == "Painel da Secretaria":
        tela_painel_secretaria()
    elif pagina == "Feed & Perfil":
        tela_perfil()


if __name__ == "__main__":
    main()
