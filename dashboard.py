"""Panel visual del sistema multiagente. Ejecutar con:  streamlit run dashboard.py"""
import matplotlib.pyplot as plt
import streamlit as st

from agentes.orquestador import AgenteOrquestador

DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


def grafico_barras(serie):
    """Barras horizontales con matplotlib (st.bar_chart usa Altair, que falla en Python 3.14)."""
    fig, ax = plt.subplots(figsize=(6, 0.45 * len(serie) + 0.8))
    serie.sort_values().plot.barh(ax=ax, color="#6b4fbb")
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_ylabel("")
    st.pyplot(fig)
    plt.close(fig)

st.set_page_config(page_title="FitFlow - Big Data con agentes", layout="wide")
st.title("FitFlow: sistema multiagente de Big Data")
st.caption("Captura → Ingesta → Almacenamiento → Análisis → Explotación, cada fase a cargo de un agente.")

with st.sidebar:
    st.header("Simulación")
    n_usuarios = st.slider("Socios", 100, 1000, 300, step=50)
    dias = st.slider("Días simulados", 45, 180, 90, step=15)


@st.cache_resource(show_spinner="Los agentes están trabajando...")
def ejecutar(n_usuarios, dias):
    orq = AgenteOrquestador(n_usuarios, dias, log=lambda *_: None)
    return orq, orq.ejecutar()


orq, r = ejecutar(n_usuarios, dias)
k = r["kpis"]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Socios", k["socios"])
c2.metric("Retención 14 días", f"{k['retencion_14d']:.0%}")
c3.metric("Visitas por semana", f"{k['visitas_por_semana']:.1f}")
c4.metric("Calificación clases", f"{k['calificacion_media_clases']:.1f} ★")
c5.metric("Socios en riesgo", k["socios_en_riesgo"])

tabs = st.tabs(["📡 Captura e ingesta", "🗄️ Almacenamiento", "🧠 Análisis", "🎯 Coach", "📊 Evaluador", "🛡️ Guardián"])

with tabs[0]:
    s = r["ingesta"]
    a, b, c, d = st.columns(4)
    a.metric("Eventos recibidos", f"{s['recibidos']:,}")
    b.metric("Válidos", f"{s['validos']:,}")
    c.metric("A cuarentena", s["invalidos"])
    d.metric("Duplicados descartados", s["duplicados"])
    st.subheader("Eventos por tipo")
    grafico_barras(r["eventos"].tipo.value_counts())
    st.subheader(f"Alertas de aforo emitidas en tiempo real ({len(r['alertas_aforo'])})")
    st.dataframe(r["alertas_aforo"], use_container_width=True)

with tabs[1]:
    st.metric("Filas con checksum alterado", r["filas_alteradas"])
    st.write("Capa **oro**: variables por socio (seudonimizadas, sin nombres).")
    st.dataframe(r["perfiles"].head(50), use_container_width=True)

with tabs[2]:
    st.subheader("Mapa de aforo promedio (personas por hora)")
    patron = r["patron_aforo"].rename(index=dict(enumerate(DIAS)))
    patron.columns = [f"{h}:00" for h in patron.columns]
    st.dataframe(patron.style.background_gradient(cmap="Purples", axis=None).format("{:.1f}"),
                 use_container_width=True)
    col1, col2 = st.columns(2)
    with col1:
        c = r["churn"]
        st.subheader("Modelo de abandono (Random Forest)")
        st.write(f"AUC **{c['auc']:.2f}** · precisión **{c['precision']:.2f}** · recall **{c['recall']:.2f}**")
        grafico_barras(c["importancias"])
    with col2:
        st.subheader("Segmentos (K-Means)")
        grafico_barras(r["perfiles"].segmento.value_counts())

with tabs[3]:
    n = r["notificaciones"]
    tipo = st.selectbox("Tipo de notificación", ["todas"] + sorted(n.tipo.unique()))
    st.dataframe(n if tipo == "todas" else n[n.tipo == tipo], use_container_width=True, hide_index=True)

with tabs[4]:
    ab = r["ab"]
    st.warning("Prueba A/B **simulada**: con usuarios reales la respuesta se mide con los check-ins.")
    a, b, c = st.columns(3)
    a.metric("Retorno con mensaje personalizado (A)", f"{ab['retorno_A']:.0%}")
    b.metric("Retorno con mensaje genérico (B)", f"{ab['retorno_B']:.0%}")
    c.metric("p-valor", f"{ab['p_valor']:.3f}", "significativo" if ab["significativo"] else "no significativo")

with tabs[5]:
    consent = orq.guardian.consentimientos.values()
    a, b, c = st.columns(3)
    a.metric("Aceptan analítica", sum(x["analitica"] for x in consent))
    b.metric("Aceptan personalización", sum(x["personalizacion"] for x in consent))
    c.metric("Consultas auditadas a la bóveda", len(orq.guardian.auditoria))
    st.write("Los agentes solo ven IDs seudónimos (`P3fa…`). La identidad real vive en la bóveda del Guardián.")
