import streamlit as st
import paho.mqtt.client as mqtt
import json
import pandas as pd
import time
from datetime import datetime
from pathlib import Path

# --- CONFIGURACIÓN ---
BROKER = "test.mosquitto.org"
PORT = 1883
TOPIC_ESTADO = "instrumentacion/estado_casino" # Tópico de monitoreo (según tu prompt)
TOPIC_COMANDOS = "instrumentacion/blackjack"   # Tópico para enviar órdenes [cite: 7]

# --- GESTIÓN DE ESTADO (Session State) ---
if "datos_casino" not in st.session_state:
    st.session_state["datos_casino"] = {}
if "ultimo_update" not in st.session_state:
    st.session_state["ultimo_update"] = "Esperando datos..."

# --- FUNCIONES MQTT ---
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Conectado al broker MQTT")
        client.subscribe(TOPIC_ESTADO)
    else:
        print(f"Error de conexión: {rc}")

def on_message(client, userdata, msg):
    """
    Callback que recibe el JSON global con todos los jugadores.
    Actualiza el estado de la sesión para que Streamlit lo renderice.
    """
    try:
        payload = msg.payload.decode()
        data = json.loads(payload)
        
        # Actualizamos el estado de Streamlit
        # Nota: En entornos complejos, usar colas es más seguro, 
        # pero para este prototipo la escritura directa funciona.
        st.session_state["datos_casino"] = data
        st.session_state["ultimo_update"] = datetime.now().strftime("%H:%M:%S")
        
    except Exception as e:
        print(f"Error procesando mensaje: {e}")

# --- INICIALIZACIÓN DEL CLIENTE MQTT (SINGLETON) ---
@st.cache_resource
def init_mqtt():
    """
    Inicializa el cliente MQTT una sola vez y lo mantiene vivo
    mientras la app de Streamlit se ejecuta.
    """
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        client.connect(BROKER, PORT, 60)
        client.loop_start() # Ejecuta el loop en un hilo separado
        return client
    except Exception as e:
        st.error(f"No se pudo conectar al broker: {e}")
        return None

client = init_mqtt()

# --- INTERFAZ STREAMLIT ---
st.set_page_config(page_title="Monitor Blackjack", layout="wide")

st.title("🎰 Monitor y Consola de Blackjack")
st.markdown(f"**Broker:** `{BROKER}` | **Estado:** `{TOPIC_ESTADO}`")

# 1. SECCIÓN DE MONITORIZACIÓN (TABLA)
st.subheader("📊 Estado de los Jugadores")

# Contenedor para la tabla que se actualizará
placeholder_tabla = st.empty()

# Lógica de renderizado de la tabla
data = st.session_state["datos_casino"]

if data:
    # Convertir el diccionario de diccionarios a DataFrame
    # orient='index' usa las claves (nombres) como índice (filas)
    df = pd.read_json(json.dumps(data), orient='index')
    
    # Reordenar columnas para mejor visualización si existen
    columnas_deseadas = ['estado', 'fondos', 'partidas', 'ganadas', 'jugador', 'crupier']
    # Filtramos solo las que existan en el df para evitar errores
    cols_finales = [c for c in columnas_deseadas if c in df.columns]
    
    # Mostrar la tabla en el placeholder
    placeholder_tabla.dataframe(df[cols_finales], use_container_width=True)
    st.caption(f"Última actualización recibida: {st.session_state['ultimo_update']}")
else:
    placeholder_tabla.info("Esperando recepción de datos JSON del casino...")

st.divider()

# 2. SECCIÓN DE CONTROL (JUGAR)
st.subheader("🎮 Enviar Comandos")

col1, col2, col3 = st.columns([2, 2, 1])

with col1:
    # Input para el nombre del jugador [cite: 10]
    nombre_jugador = st.text_input("Nombre del Jugador", value="jugador_st_01")

with col2:
    # Selector de acción posible 
    accion_seleccionada = st.selectbox(
        "Acción", 
        options=["nueva", "carta", "planto"],
        format_func=lambda x: x.upper()
    )

with col3:
    st.write("Confirmar:")
    enviar = st.button("Enviar Orden 🚀", use_container_width=True)

if enviar:
    if client:
        # Construcción del JSON según requisitos del usuario
        # Nota: El usuario especificó "accion" (sin tilde) para la key.
        payload = {
            "jugador": nombre_jugador,
            "accion": accion_seleccionada  # Sin tilde según tu instrucción
        }
        
        mensaje_json = json.dumps(payload)
        client.publish(TOPIC_COMANDOS, mensaje_json)
        
        st.toast(f"Enviado: {mensaje_json} a {TOPIC_COMANDOS}")
    else:
        st.error("Error: No hay conexión MQTT")