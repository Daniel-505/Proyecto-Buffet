from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import mysql.connector
from mysql.connector import errorcode

app = Flask(__name__)
CORS(app) # Permite que el Dashboard Web acceda a la API desde otra IP/Puerto

# --- CONFIGURACIÓN DE LA BASE DE DATOS (¡AJUSTA ESTO!) ---
DB_CONFIG = {
    'user': 'dtrr', 
    'password': '2mas2es4',
    'host': '10.56.2.71', # Si Flask y MariaDB están en el mismo servidor
    'database': 'nombre_base_datos_semaforo'
}

# --- FUNCIÓN PARA CONECTAR A DB ---
def get_db_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as err:
        print(f"Error al conectar a MariaDB: {err}")
        # En la consola de VS Code/Terminal, este error es lo que te indica que el servidor 10.56.2.71 no responde.
        return None

# --- FUNCIÓN PARA ASEGURAR LA TABLA (CREARLA SI NO EXISTE) ---
def ensure_db_structure():
    conn = get_db_connection()
    if conn is None: 
        print("No se pudo conectar a la BD para asegurar la estructura.")
        return

    cursor = conn.cursor()
    TABLES = {}
    TABLES['registros_servicio'] = (
        "CREATE TABLE `registros_servicio` ("
        "  `id` INT NOT NULL AUTO_INCREMENT,"
        "  `timestamp` DATETIME NOT NULL,"
        "  `ciclo_id` INT NOT NULL,"
        "  `duracion_servicio_s` INT NOT NULL,"
        "  `duracion_espera_s` INT NOT NULL,"
        "  `finalizacion_tipo` VARCHAR(20) NOT NULL,"
        "  PRIMARY KEY (`id`)"
        ") ENGINE=InnoDB")
    
    # Intenta crear la tabla
    try:
        cursor.execute(TABLES['registros_servicio'])
        print("Tabla 'registros_servicio' creada exitosamente.")
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_TABLE_EXISTS_ERROR:
            pass # La tabla ya existe, no hacemos nada
        else:
            print(f"Error al crear la tabla: {err.msg}")
    
    cursor.close()
    conn.close()

# -----------------------------------------------------------------
# --- NUEVA RUTA: PÁGINA PRINCIPAL (Sirve el HTML) ---
# -----------------------------------------------------------------
@app.route('/', methods=['GET'])
def index():
    """ Sirve el archivo HTML principal (Dashboard). """
    return render_template('dashboard.html')
# -----------------------------------------------------------------

# --- ENDPOINT 1: RECEPCIÓN DE DATOS DEL ESP32 (POST) ---
@app.route('/api/registrar_ciclo', methods=['POST'])
def registrar_ciclo():
    """ Recibe los datos JSON del ESP32. """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON no válido"}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "No se pudo conectar a la base de datos"}), 503

    try:
        cursor = conn.cursor()
        sql = """INSERT INTO registros_servicio 
                 (timestamp, ciclo_id, duracion_servicio_s, duracion_espera_s, finalizacion_tipo) 
                 VALUES (NOW(), %s, %s, %s, %s)"""
                 
        valores = (
            data.get('ciclo_id'), 
            data.get('duracion_servicio_s'), 
            data.get('duracion_espera_s'), 
            data.get('finalizacion_tipo')
        )
        
        cursor.execute(sql, valores)
        conn.commit()

        return jsonify({"mensaje": "Registro guardado exitosamente"}), 201

    except Exception as e:
        print(f"Error al procesar el registro: {e}")
        return jsonify({"error": "Error interno del servidor", "detalle": str(e)}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


# --- ENDPOINT 2: ENVÍO DE DATOS A LA WEB (GET) ---
@app.route('/api/obtener_registros', methods=['GET'])
def obtener_registros():
    """ Envía TODOS los registros al Dashboard Web. """
    conn = get_db_connection()
    if conn is None:
        # Devuelve un JSON vacío o un mensaje de error si la conexión falla
        return jsonify({"error": "No se pudo conectar a la base de datos", "registros": []}), 503

    try:
        # Usamos dictionary=True para obtener resultados como diccionarios (JSON-friendly)
        cursor = conn.cursor(dictionary=True) 
        
        # Selecciona los registros más recientes
        cursor.execute("SELECT * FROM registros_servicio ORDER BY timestamp DESC LIMIT 100")
        registros = cursor.fetchall()
        
        # Formatea el campo 'timestamp' a string ISO 8601 para que JSON lo pueda manejar
        for registro in registros:
            if registro['timestamp']:
                registro['timestamp'] = registro['timestamp'].isoformat()
        
        return jsonify(registros)

    except Exception as e:
        print(f"Error al obtener datos: {e}")
        return jsonify({"error": "Error al obtener datos", "detalle": str(e), "registros": []}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# --- RUN APP ---
if __name__ == '__main__':
    ensure_db_structure() # Asegura que la tabla exista al iniciar
    # Escucha en todas las interfaces (0.0.0.0) para que el ESP32 y el frontend puedan acceder
    print("Servidor Flask corriendo. Accede al dashboard en http://127.0.0.1:5000/")
    app.run(host='0.0.0.0', port=5000, debug=True)