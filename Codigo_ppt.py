import streamlit as st
import pandas as pd
import plotly.express as px

# ==========================================
# 1. CONFIGURACIÓN DE PÁGINA
# ==========================================
st.set_page_config(
    page_title="Monitor análisis de deserción",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("Monitor análisis de deserción")
st.markdown("""
Dashboard de análisis basado en costos reales 2017, motivación estudiantil y origen geográfico.
**Criterios de Riesgo:** Motivación < 3.2 | Costo > $3.8M | Estudiante Foráneo.
""")

# ==========================================
# 2. CARGA DE DATOS (CON CACHÉ)
# ==========================================
@st.cache_data
def cargar_datos():
    # Función de lectura robusta
    def leer_csv(ruta, sep1, sep2):
        try:
            return pd.read_csv(ruta, sep=sep1, encoding='utf-8', on_bad_lines='skip')
        except:
            return pd.read_csv(ruta, sep=sep2, encoding='latin1', on_bad_lines='skip')

    df_mat = leer_csv('20250729_Matrícula_Ed_Superior_2017_PUBL_MRUN_RESUMIDO.csv', ';', ',')
    df_enc = leer_csv('Cuestionario motivacion academica.csv', ',', ';')
    df_uinn = leer_csv('Data_UINN_Facultad.csv', ';', ',')
    
    # Limpieza
    df_mat.columns = df_mat.columns.str.strip()
    df_enc.columns = df_enc.columns.str.strip()
    df_uinn.columns = df_uinn.columns.str.strip()

    # --- COSTOS REALES 2017 ---
    ARANCEL_CIVILES_2017 = 3419000 
    mapa_costos_reales = {
        'Ing. Civil Industrial': ARANCEL_CIVILES_2017,
        'Ingeniería Civil': ARANCEL_CIVILES_2017,
        'Ing. Civil Eléctrica': ARANCEL_CIVILES_2017,
        'Ing. Civil Electrónica': ARANCEL_CIVILES_2017,
        'Ing. Civil Informática': ARANCEL_CIVILES_2017,
        'Ingeniería Comercial': 3419000
    }

    # --- MAPEO DE CARRERAS ---
    mapa_nombres = {
        3309: 'Ing. Civil Industrial',
        3310: 'Ingeniería Civil',
        3311: 'Ing. Civil Eléctrica',
        3318: 'Ing. Civil Electrónica',
        3303: 'Ingeniería Comercial',
        3319: 'Ing. Civil Informática'
    }

    # Procesar Cuestionario
    col_udec = df_enc.columns[0]
    df_enc[col_udec] = pd.to_numeric(df_enc[col_udec], errors='coerce')
    df_enc = df_enc[df_enc[col_udec].isin(mapa_nombres.keys())].copy()

    # Asignar datos
    df_enc['Carrera'] = df_enc[col_udec].map(mapa_nombres)
    df_enc['Costo_Real'] = df_enc['Carrera'].map(mapa_costos_reales)

    # Zonas
    def get_zona(ciudad):
        c = str(ciudad).lower()
        if any(x in c for x in ['arica','iquique','antofagasta','calama','serena']): return 'Zona Norte'
        if any(x in c for x in ['temuco','valdivia','osorno','montt','chiloe','coyhaique','aysen']): return 'Zona Sur'
        if any(x in c for x in ['concepción','talcahuano','penco','chiguayante','coronel']): return 'Zona Local'
        return 'Zona Centro'

    df_enc['Zona'] = df_enc.iloc[:, 1].apply(get_zona)
    df_enc['Es_Foraneo'] = df_enc['Zona'].isin(['Zona Norte', 'Zona Sur'])

    # Motivación
    cols_preg = df_enc.columns[5:16]
    for c in cols_preg: df_enc[c] = pd.to_numeric(df_enc[c], errors='coerce')
    df_enc['Motivacion'] = df_enc[cols_preg].mean(axis=1)

    # --- CÁLCULO DE RIESGO ESTÁNDAR (YA NO ES DINÁMICO) ---
    def calcular_riesgo_fijo(row):
        pts = 0
        if row['Motivacion'] < 3.2: pts += 1.0       # Umbral fijo
        if row['Costo_Real'] > 3800000: pts += 0.5   # Umbral fijo
        if row['Es_Foraneo']: pts += 0.5             # Umbral fijo
        
        return 1 if pts >= 1.5 else 0

    df_enc['En_Riesgo'] = df_enc.apply(calcular_riesgo_fijo, axis=1)

    return df_enc

try:
    df_base = cargar_datos()
except Exception as e:
    st.error(f"Error cargando datos: {e}")
    st.stop()

# ==========================================
# 3. BARRA LATERAL (SOLO FILTROS VISUALES)
# ==========================================
st.sidebar.header("Filtros de Visualización")

# Filtro por Carrera
todas_carreras = sorted(df_base['Carrera'].unique())
carreras_selec = st.sidebar.multiselect(
    "Filtrar por Carrera:", 
    options=todas_carreras,
    default=todas_carreras
)

# Filtro por Zona
todas_zonas = sorted(df_base['Zona'].unique())
zonas_selec = st.sidebar.multiselect(
    "Filtrar por Zona:",
    options=todas_zonas,
    default=todas_zonas
)

# Aplicar Filtros
df_filtrado = df_base[
    (df_base['Carrera'].isin(carreras_selec)) & 
    (df_base['Zona'].isin(zonas_selec))
].copy()

# ==========================================
# 4. VISUALIZACIÓN EN PESTAÑAS
# ==========================================

tab1, tab2, tab3 = st.tabs(["Datos en General", "Análisis Geográfico", "Datos Detallados"])

with tab1:
    # --- KPIS ---
    if not df_filtrado.empty:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Muestra Analizada", len(df_filtrado))
        col2.metric("Tasa de Riesgo", f"{(df_filtrado['En_Riesgo'].mean()*100):.1f}%")
        col3.metric("Costo Promedio", f"${df_filtrado['Costo_Real'].mean():,.0f}")
        col4.metric("Motivación Promedio", f"{df_filtrado['Motivacion'].mean():.2f}")
    else:
        st.warning("No hay datos con los filtros seleccionados.")

    st.divider()

    # --- GRÁFICO 1: BURBUJAS ---
    if not df_filtrado.empty:
        df_carrera = df_filtrado.groupby('Carrera').agg({
            'Costo_Real': 'mean',
            'Motivacion': 'mean',
            'En_Riesgo': lambda x: (x.sum() / len(x)) * 100,
            'Es_Foraneo': lambda x: (x.sum() / len(x)) * 100
        }).reset_index()

        fig1 = px.scatter(df_carrera, 
                        x="Costo_Real", 
                        y="En_Riesgo",
                        size="Es_Foraneo",
                        color="Motivacion",
                        text="Carrera",
                        title="Matriz de Riesgo: Costo vs. Deserción Probable",
                        labels={'Costo_Real': 'Costo Real ($)', 'En_Riesgo': '% Tasa Riesgo'},
                        color_continuous_scale="RdYlGn",
                        height=500)
        fig1.update_traces(textposition='top center')
        st.plotly_chart(fig1, use_container_width=True)

with tab2:
    col_g1, col_g2 = st.columns(2)
    
    with col_g1:
        # Gráfico Riesgo por Zona
        df_zona = df_filtrado.groupby('Zona')['En_Riesgo'].mean().reset_index()
        df_zona['En_Riesgo'] *= 100
        
        fig2 = px.bar(df_zona, x="Zona", y="En_Riesgo", color="Zona",
                    title="Tasa de Riesgo por Zona",
                    text_auto='.1f', labels={'En_Riesgo': '% Riesgo'})
        st.plotly_chart(fig2, use_container_width=True)
        
    with col_g2:
        # Gráfico Motivación por Zona
        df_motiv = df_filtrado.groupby('Zona')['Motivacion'].mean().reset_index()
        
        fig3 = px.bar(df_motiv, x="Zona", y="Motivacion", color="Zona",
                    title="Motivación Promedio por Zona",
                    text_auto='.2f', range_y=[1,5])
        st.plotly_chart(fig3, use_container_width=True)

with tab3:
    st.subheader("Resumen de Datos")
    
    # Crear una tabla resumen agrupada
    tabla_resumen = df_filtrado.groupby(['Carrera', 'Zona']).agg(
        Estudiantes=('Motivacion', 'count'),
        Motivacion=('Motivacion', 'mean'),
        Riesgo=('En_Riesgo', lambda x: f"{(x.mean()*100):.1f}%"),
        Costo=('Costo_Real', 'mean')
    ).reset_index()
    
    st.dataframe(tabla_resumen, use_container_width=True)