import os
import importlib
import sys
import time
import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import pygame


# el proyecto usa la version 3.14.5 de python
# se puede actualizar python desde el CMD usando el comando:
# "python -m pip install --upgrade pip"

# el proyecto usa opencv, mediapipe(0.10.35) y
# pygame-ce (que es una version pygame de la comunidad que funciona con esta version de python)
# estas dependencias se pueden instalar desde el CMD con el comando:
# "pip install opencv-python==4.13.0.92 mediapipe==0.10.35 pygame-ce"


# si se quiere instalar el compilador, en el CMD use:
# "pip install pyinstaller"

# para compilar el proyecto, hay que ir a la carpeta raiz a traves del CMD y ejecutar el comando:
# "pyinstaller --onefile --noconsole --add-data "face_landmarker.task;." --add-data "hand_landmarker.task;." --add-data "games;games" main.py"




# CONFIGURACIÓN INICIAL DE PYGAME
pygame.init()
info = pygame.display.Info()
ANCHO_PANTALLA, ALTO_PANTALLA = info.current_w, info.current_h
ANCHO_PANTALLA, ALTO_PANTALLA = 960, 720
pantalla = pygame.display.set_mode((ANCHO_PANTALLA, ALTO_PANTALLA), pygame.SCALED | pygame.FULLSCREEN)
pygame.display.set_caption("sistema de Control")

pygame.mouse.set_visible(False) # oculta el mouse

def resolver_ruta(ruta_relativa):
    """
    resuelve rutas de archivos tanto en desarrollo como si el script se empaqueta (.exe)
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, ruta_relativa)
    return os.path.join(os.path.abspath("."), ruta_relativa)

# VARIABLES GLOBALES DE IA Y FILTROS
detector = None  # almacena el objeto Landmarker activo de mediapipe
MODO_ACTIVO = None

# mediapipe entrega coordenadas normalizadas
# estas variables guardan los límites espaciales para mapear ese rango al tamaño de la pantalla
calib_min_x, calib_max_x = 0.4, 0.6
calib_min_y, calib_max_y = 0.4, 0.6

# historial para aplicar un filtro de media móvil y suavizar el temblor del cursor
historial_x, historial_y = [], []
LARGO_FILTRO = 15
mouse_actual_x, mouse_actual_y = ANCHO_PANTALLA // 2, ALTO_PANTALLA // 2
VELOCIDAD_MOUSE = 0.12  # interpolación lineal para suavizado

contador_click = 0
UMBRAL_CONSECUTIVOS = 2  # evita falsos positivos requiriendo que el gesto dure N frames
juego_actual_modulo = None

# PANTALLA DE CARGA
def mostrar_pantalla_carga(mensaje):
    pantalla.fill((20, 20, 30))
    fuente = pygame.font.SysFont("Arial", 40)
    texto = fuente.render(mensaje, True, (255, 255, 255))
    pantalla.blit(texto, (ANCHO_PANTALLA // 2 - texto.get_width() // 2, ALTO_PANTALLA // 2 - texto.get_height() // 2))
    pygame.display.flip()

# MENU DE SELECCIÓN INICIAL (POR TECLADO)
def menu_seleccion_modo():
    """
    configura e inicializa las extenciones de mediapipe (FaceLandmarker o HandLandmarker)
    según la elección del usuario, cargando sus respectivos archivos (.task)
    """
    global detector, MODO_ACTIVO, historial_x, historial_y
    
    fuente_tit = pygame.font.SysFont("Arial", 40, bold=True)
    fuente_opt = pygame.font.SysFont("Arial", 30)
    
    opciones = [
        "Seleccione usando las teclas numericas:",
        "1. Mano Izquierda (Gesto: Puño)",
        "2. Mano Derecha (Gesto: Puño)",
        "3. Ojo Izquierdo (Gesto: Parpadeo)",
        "4. Ojo Derecho (Gesto: Parpadeo)",
        "5. Usar el ratón"
    ]
    
    seleccion = None
    while seleccion is None:
        pantalla.fill((25, 25, 35))
        txt = fuente_tit.render("SELECCIONA EL MODO DE CONTROL", True, (255, 255, 255))
        pantalla.blit(txt, (ANCHO_PANTALLA // 2 - txt.get_width() // 2, 150))
        
        for i, opt in enumerate(opciones):
            txt_opt = fuente_opt.render(opt, True, (200, 200, 200))
            pantalla.blit(txt_opt, (ANCHO_PANTALLA // 2 - 200, 280 + (i * 60)))
            
        pygame.display.flip()
        
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_1: seleccion = "mano_izq"
                if evento.key == pygame.K_2: seleccion = "mano_der"
                if evento.key == pygame.K_3: seleccion = "ojo_izq"
                if evento.key == pygame.K_4: seleccion = "ojo_der"
                if evento.key == pygame.K_5: seleccion = "raton"
                if evento.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                    
    MODO_ACTIVO = seleccion
    historial_x.clear()
    historial_y.clear()
    
    # CONFIGURACIÓN DE LAS EXTENCIONES DE MEDIAPIPE
    # RunningMode.VIDEO para procesar un flujo continuo de frames
    if "ojo" in MODO_ACTIVO:
        options = vision.FaceLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=resolver_ruta('face_landmarker.task')),
            running_mode=vision.RunningMode.VIDEO, 
            output_face_blendshapes=True  # para obtener metricas detalladas de expresiones (ej. parpadeos)
        )
        detector = vision.FaceLandmarker.create_from_options(options)
    elif "mano" in MODO_ACTIVO:
        options = vision.HandLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=resolver_ruta('hand_landmarker.task')),
            running_mode=vision.RunningMode.VIDEO, 
            num_hands=2
        )
        detector = vision.HandLandmarker.create_from_options(options)

# FUNCIÓN PARA OBTENER COORDENADAS
def procesar_frame_ia(frame, timestamp):
    """
    Toma un frame de opencv, lo adapta al formato de mediapipe y extrae la información espacial.
    
    argumentos:
        frame: matriz NumPy en formato BGR (nativo de opencv).
        timestamp: Tiempo de ejecución en milisegundos (requerido por RunningMode.VIDEO).
    """
    # 1. opencv trabaja en formato BGR. mediapipe requiere RGB
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # 2. convierte el array de pixeles en un objeto de imagen compatible con mediapipe
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
    
    # 3. inferencia del modelo pasándole la imagen y el tiempo exacto del frame
    res = detector.detect_for_video(mp_image, timestamp)
    
    x, y, detectado, click = None, None, False, False
    
    # PROCESAMIENTO DE ROSTRO
    if "ojo" in MODO_ACTIVO and res.face_landmarks:
        detectado = True
        landmarks = res.face_landmarks[0]
        # el landmark 468 corresponde al centro del iris izquierdo y el landmark 473 al iris derecho
        punto = landmarks[468] if MODO_ACTIVO == "ojo_izq" else landmarks[473]
        x, y = punto.x, punto.y  # coordenadas relativas
        
        # uso el blendshapes para tracking del gesto preciso sin depender de distancias métricas
        if res.face_blendshapes:
            shape_name = "eyeBlinkLeft" if MODO_ACTIVO == "ojo_izq" else "eyeBlinkRight"
            for shape in res.face_blendshapes[0]:
                # Si el parpadeo supera el umbral (0.45), se interpreta como click
                if shape.category_name == shape_name and shape.score > 0.45:
                    click = True

    # PROCESAMIENTO DE MANOS
    elif "mano" in MODO_ACTIVO and res.hand_landmarks:
        for i, hand_info in enumerate(res.handedness):
            # mediapipe invierte las etiquetas izquierda/derecha debido al modo espejo de las cámaras
            mano_detectada = hand_info[0].category_name.lower()
            objetivo_mano = "right" if MODO_ACTIVO == "mano_izq" else "left"
            
            if mano_detectada == objetivo_mano:
                detectado = True
                landmarks = res.hand_landmarks[i]
                
                # se usa el Landmark 9 (Nudillo del dedo medio) como el centro de la mano para mover el cursor
                x, y = landmarks[9].x, landmarks[9].y
                
                # compara si la punta de cada dedo está por debajo de su respectivo nudillo
                puntas = [8, 12, 16, 20]
                nudillos = [6, 10, 14, 18]
                cerrados = 0
                for p, n in zip(puntas, nudillos):
                    if landmarks[p].y > landmarks[n].y: 
                        cerrados += 1
                
                if cerrados == 4: 
                    click = True
                break
                
    return x, y, detectado, click

# CALIBRACION
def ejecutar_calibracion_visual(cap):
    """
    calcula los límites espaciales (mínimo y máximo) del movimiento del usuario
    Permite escalar el espacio físico relativo al espacio absoluto de pixeles de la pantalla
    """
    global calib_min_x, calib_min_y, calib_max_x, calib_max_y
    elemento_a_mirar = "tu MANO" if "mano" in MODO_ACTIVO else "tu OJO"
    pasos = [
        {"msg": f"1. Lleva {elemento_a_mirar} a la esquina SUPERIOR IZQUIERDA", "tipo": "min"},
        {"msg": f"2. Lleva {elemento_a_mirar} a la esquina INFERIOR DERECHA", "tipo": "max"}
    ]
    
    for paso in pasos:
        capturado = False
        while not capturado:
            success, frame = cap.read()
            if not success: 
                break
            
            # espejar el frame horizontalmente (1) para que el movimiento de la pantalla sea intuitivo
            frame = cv2.flip(frame, 1)
            
            t = int(time.time() * 1000)
            x, y, detectado, _ = procesar_frame_ia(frame, t)
            
            if detectado:
                # conversión de normalizado a pixeles de la ventana de opencv para el dibujado
                ix, iy = int(x * frame.shape[1]), int(y * frame.shape[0])
                cv2.circle(frame, (ix, iy), 6, (0, 255, 0), -1)

            # se inserta el texto informativo directo sobre la imagen usando opencv
            color_txt = (0, 255, 0) if detectado else (0, 0, 255)
            cv2.putText(frame, paso["msg"], (15, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_txt, 2)
            if detectado:
                cv2.putText(frame, "Presiona ENTER para capturar", (15, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # renderizado del flujo de video procesado en una ventana nativa de opencv
            cv2.imshow('Calibracion del Sistema', frame)
            
            # control de frecuencia de teclado obligatorio en opencv para refrescar ventanas
            key = cv2.waitKey(1) & 0xFF
            if key == 13 and detectado:  # 13 representa la tecla Enter en código ASCII
                if paso["tipo"] == "min": 
                    calib_min_x, calib_min_y = x, y
                else: 
                    calib_max_x, calib_max_y = x, y
                capturado = True
                
    cv2.destroyAllWindows()
    cv2.waitKey(1)

def listar_juegos():
    carpeta_raiz = resolver_ruta("games")
    if not os.path.exists(carpeta_raiz): 
        os.makedirs(carpeta_raiz)
    return [e for e in os.listdir(carpeta_raiz) if os.path.isdir(os.path.join(carpeta_raiz, e)) and not e.startswith("__")]

def lanzar_juego(nombre_carpeta):
    global juego_actual_modulo
    try:
        modulo = importlib.import_module(f"games.{nombre_carpeta}.start")
        importlib.reload(modulo)
        modulo.iniciar(pantalla, None)
        juego_actual_modulo = modulo
    except Exception as e: 
        print(f"Error: {e}")

# BUCLE PRINCIPAL
def menu_principal():
    global mouse_actual_x, mouse_actual_y, contador_click, juego_actual_modulo
    
    menu_seleccion_modo()
    
    if not "raton" in MODO_ACTIVO:
        mostrar_pantalla_carga("Iniciando cámara web...")

        # CONEXIÓN DE HARDWARE CON OPENCV
        cap = cv2.VideoCapture(0)  # abre la webcam por defecto (índice 0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)  # define resolución horizontal
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)   # define resolución vertical
        time.sleep(1)  # pausa para permitir que el hardware de la camara se estabilice
        
        ejecutar_calibracion_visual(cap)

    fuente_titulo = pygame.font.SysFont("Arial", 40, bold=True)
    fuente_opciones = pygame.font.SysFont("Arial", 28)
    clock = pygame.time.Clock()
    
    ejecutando = True
    while ejecutando:
        clock.tick(30) # limita los fps del programa
        lista_juegos = listar_juegos()
        
        click_confirmado = False

        if "raton" in MODO_ACTIVO:
            mouse_actual_x, mouse_actual_y = pygame.mouse.get_pos()
        else:
            # lectura sincrónica del flujo de la cámara (success indica si el hardware entregó el búfer)
            success, frame = cap.read()

            if success:
                frame = cv2.flip(frame, 1)  # espejado horizontal continuo
                t = int(time.time() * 1000)
                x, y, detectado, click_activo = procesar_frame_ia(frame, t)

                if detectado:
                    # MAPEO Y ESCALADO
                    # transforma las coordenadas relativas del modelo acotándolas al rango calibrado por el usuario
                    rango_x = calib_max_x - calib_min_x
                    rango_y = calib_max_y - calib_min_y
                    if rango_x != 0 and rango_y != 0:
                        # normalización local en función de los mínimos/máximos capturados
                        prop_x = max(0.0, min(1.0, (x - calib_min_x) / rango_x))
                        prop_y = max(0.0, min(1.0, (y - calib_min_y) / rango_y))

                        # almacenamiento en búfer para filtrado por promedio (suavizado de ruido)
                        historial_x.append(int(prop_x * ANCHO_PANTALLA))
                        historial_y.append(int(prop_y * ALTO_PANTALLA))
                        if len(historial_x) > LARGO_FILTRO:
                            historial_x.pop(0)
                            historial_y.pop(0)

                        # interpolación lineal: se mueve un % de distancia hacia el nuevo objetivo por frame
                        mouse_actual_x += (sum(historial_x)/len(historial_x) - mouse_actual_x) * VELOCIDAD_MOUSE
                        mouse_actual_y += (sum(historial_y)/len(historial_y) - mouse_actual_y) * VELOCIDAD_MOUSE

                    # debounce y lógica para controlar el disparo único del evento de click por gestos discretos
                    if click_activo: 
                        contador_click += 1
                    else:
                        if contador_click >= UMBRAL_CONSECUTIVOS: 
                            click_confirmado = True
                        contador_click = 0


        # GESTIÓN DE EVENTOS DE PYGAME
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT: 
                ejecutando = False
            
            if evento.type == pygame.MOUSEBUTTONDOWN:
                if evento.button == 1:
                    click_confirmado = True
            
            if evento.type == pygame.KEYDOWN:
                # Si presiona ESCAPE
                if evento.key == pygame.K_ESCAPE:
                    if juego_actual_modulo is not None: 
                        pygame.mixer.music.stop()
                        juego_actual_modulo = None  # Salir del juego al menu
                    else: 
                        ejecutando = False         # Cerrar programa si está en el menu
                
                elif evento.key == pygame.K_SPACE:
                    # Solo permite recalibrar si no hay un juego activo (osea está en el menu)
                    if juego_actual_modulo is None:
                        print("Recalibración solicitada por teclado (ESPACIO)")
                        
                        if not "raton" in MODO_ACTIVO:
                            # apaga la camara y limpia pantalla
                            cap.release()
                        cv2.destroyAllWindows()
                        
                        # vuelve a pedir el modo por teclado
                        menu_seleccion_modo()
                        
                        if not "raton" in MODO_ACTIVO:
                            # reinicia la cámara con su cartel de carga
                            mostrar_pantalla_carga("Reiniciando cámara web...")
                            cap = cv2.VideoCapture(0)
                            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                            time.sleep(1)

                            # lanza la calibración visual en base al nuevo modo
                            ejecutar_calibracion_visual(cap)

        if juego_actual_modulo is not None:
            # bucle dentro del juego
            juego_actual_modulo.actualizar_y_dibujar(pantalla, mouse_actual_x, mouse_actual_y, click_confirmado)
        else:
            pantalla.fill((20, 20, 30))
            txt_tit = fuente_titulo.render(f"MENU PRINCIPAL ({MODO_ACTIVO.upper()})", True, (255, 255, 255))
            pantalla.blit(txt_tit, (ANCHO_PANTALLA // 2 - txt_tit.get_width() // 2, 60))
            
            juego_sel = None
            accion_cambiar_modo = False
            
            for i, juego in enumerate(lista_juegos):
                rect_btn = pygame.Rect(ANCHO_PANTALLA // 2 - 225, 180 + (i * 85), 450, 55)
                color_btn = (0, 200, 100) if rect_btn.collidepoint(mouse_actual_x, mouse_actual_y) else (50, 50, 70)
                if rect_btn.collidepoint(mouse_actual_x, mouse_actual_y): 
                    juego_sel = juego
                
                pygame.draw.rect(pantalla, color_btn, rect_btn, border_radius=10)
                txt_juego = fuente_opciones.render(juego.replace("_", " ").upper(), True, (255, 255, 255))
                pantalla.blit(txt_juego, (rect_btn.x + 20, rect_btn.y + 27 - txt_juego.get_height() // 2))

            y_btn_cambio = 200 + (len(lista_juegos) * 85)
            rect_cambio = pygame.Rect(ANCHO_PANTALLA // 2 - 225, y_btn_cambio, 450, 55)
            color_cambio = (220, 130, 0) if rect_cambio.collidepoint(mouse_actual_x, mouse_actual_y) else (90, 60, 40)
            if rect_cambio.collidepoint(mouse_actual_x, mouse_actual_y): 
                accion_cambiar_modo = True
                
            pygame.draw.rect(pantalla, color_cambio, rect_cambio, border_radius=10)
            txt_cambio = fuente_opciones.render("CAMBIAR MODO DE CONTROL", True, (255, 255, 255))
            pantalla.blit(txt_cambio, (rect_cambio.x + 20, rect_cambio.y + 27 - txt_cambio.get_height() // 2))

            if click_confirmado:
                if juego_sel:
                    lanzar_juego(juego_sel)
                elif accion_cambiar_modo:
                    # se cierra el canal de captura activo antes de reconfigurar para evitar bloqueos del Video
                    cap.release()
                    cv2.destroyAllWindows()
                    
                    menu_seleccion_modo()
                    
                    mostrar_pantalla_carga("Reiniciando cámara web...")
                    cap = cv2.VideoCapture(0)
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                    time.sleep(1)
                    
                    ejecutar_calibracion_visual(cap)

            pygame.draw.circle(pantalla, (255, 50, 50), (int(mouse_actual_x), int(mouse_actual_y)), 12)
            pygame.draw.circle(pantalla, (255, 255, 255), (int(mouse_actual_x), int(mouse_actual_y)), 12, 2)

        pygame.display.flip()

    # cierre total del pipeline de video e hilos de captura de opencv al terminar la ejecución
    if not "raton" in MODO_ACTIVO:
        cap.release()
    pygame.quit()

if __name__ == "__main__":
    menu_principal()