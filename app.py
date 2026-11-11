import os
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from time import sleep

app = Flask(__name__)
app.config['SECRET_KEY'] = 'aula_secret_key_123'

socketio = SocketIO(app, cors_allowed_origins="*")

# Estado global del Aula
estado_aula = {
    "luz": False,
    "ventilador": False,
    "puerta": "cerrada",
    "presencia": False,
    "temperatura": 22.5
}

# Configuración de Hardware Real en Raspberry Pi
try:
    from gpiozero import LED, Servo, MotionSensor
    ES_RASPBERRY = True
    
    # Declaración de pines GPIO
    luz_aula = LED(17)        # Pin 11 físico
    ventilador = LED(22)      # Pin 15 físico (Relé)
    puerta_servo = Servo(18)  # Pin 12 físico
    sensor_pir = MotionSensor(27) # Pin 13 físico
    
    print("HARDWARE REAL CONECTADO: Control de pines GPIO activo")
except (ImportError, Exception) as e:
    ES_RASPBERRY = False
    print(f"MODO SIMULACIÓN (Error al cargar GPIO: {e})")


# --- AUTOMATIZACIÓN DEL SENSOR PIR ---
def configurar_eventos_hardware():
    if ES_RASPBERRY:
        def al_detectar_movimiento():
            print("PIR: Movimiento detectado en el aula física")
            estado_aula['presencia'] = True
            
            # Regla automática: si la luz está apagada, encenderla
            if not estado_aula['luz']:
                estado_aula['luz'] = True
                luz_aula.on()
                socketio.emit('evento_estado_cambiado', {'dispositivo': 'luz', 'estado': True})
                
            socketio.emit('evento_sensor_disparado', {'tipo': 'presencia', 'valor': True})

        def al_cesar_movimiento():
            print("PIR: Sin movimiento")
            estado_aula['presencia'] = False
            socketio.emit('evento_sensor_disparado', {'tipo': 'presencia', 'valor': False})

        sensor_pir.when_motion = al_detectar_movimiento
        sensor_pir.when_no_motion = al_cesar_movimiento


# --- RUTAS DE NAVEGACIÓN WEB ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/niveles')
def niveles():
    return render_template('niveles.html')

@app.route('/lecturas')
def lecturas():
    return render_template('lecturas.html')


# --- SOCKET.IO (Control en tiempo real) ---
@socketio.on('connect')
def al_conectar():
    print("Cliente web conectado al servidor")
    emit('estado_inicial', estado_aula)

@socketio.on('comando_dispositivo')
def manejar_comando(data):
    dispositivo = data.get('dispositivo')
    accion = data.get('accion')

    print(f"Orden desde la web: [{dispositivo}] -> {accion}")

    if dispositivo == 'luz':
        nuevo_estado = (accion == 'encender')
        estado_aula['luz'] = nuevo_estado
        if ES_RASPBERRY:
            luz_aula.on() if nuevo_estado else luz_aula.off()

    elif dispositivo == 'ventilador':
        nuevo_estado = (accion == 'encender')
        estado_aula['ventilador'] = nuevo_estado
        if ES_RASPBERRY:
            ventilador.on() if nuevo_estado else ventilador.off()

    elif dispositivo == 'puerta':
        estado_aula['puerta'] = 'abierta' if accion == 'abrir' else 'cerrada'
        if ES_RASPBERRY:
            if accion == 'abrir':
                puerta_servo.max()
            else:
                puerta_servo.min()
            
            # Esperamos a que termine el giro y cortamos el pulso para evitar el temblor
            sleep(0.5)
            puerta_servo.detach()

    emit('evento_estado_cambiado', {
        'dispositivo': dispositivo,
        'estado': estado_aula[dispositivo]
    }, broadcast=True)


if __name__ == '__main__':
    configurar_eventos_hardware()
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False)