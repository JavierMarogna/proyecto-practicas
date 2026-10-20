import pygame
import os
import sys

# esta funcion debe estar en todo juego y usarse cuando se quiere llamar un recurso
def resolver_ruta_local(archivo_recurso):
    """ encuentra recursos dentro de la misma carpeta del juego y hace que la ruta funcione cuando esta compilado """
    if hasattr(sys, '_MEIPASS'):
        # en el .exe compilado, todas las carpetas se van en la ruta temporal
        # 'os.path.dirname(__file__)' da la ubicacion exacta de este start.py
        return os.path.join(os.path.dirname(__file__), archivo_recurso)
    
    # en modo desarrollo normal (.py suelto)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), archivo_recurso)

# crea una clase para guardar el estado del juego
class EstadoJuego:
    def __init__(self):
        self.puntuacion = 0
        self.pos_objetivo = [200, 200]
        self.imagen_blanco = None
        self.sonido_click = None

estado = EstadoJuego()

def iniciar(pantalla, juego_vuelve_al_menu):
    """main.py llama esta funcion UNA VEZ cuando el juego arranca"""
    print("Juego inicializado")
    # dentro de esta funcion cargar sonidos o imagenes del juego


    # cargar imagen
    ruta_img = resolver_ruta_local("blanco.png")
    imagen_original = pygame.image.load(ruta_img).convert_alpha()

    #cambia el tamaño de la imagen
    estado.imagen_blanco = pygame.transform.scale(imagen_original, (300, 300))
    
    # cargar efecto de sonido
    ruta_sfx = resolver_ruta_local(os.path.join("disparo.wav"))
    estado.sonido_click = pygame.mixer.Sound(ruta_sfx)
    estado.sonido_click.set_volume(0.3)

    # cargar musica
    ruta_sound = resolver_ruta_local("musica.mp3")
    pygame.mixer.music.load(ruta_sound)
    pygame.mixer.music.set_volume(0.8)
    pygame.mixer.music.play(-1) # -1 hace que la musica se repita en bucle

def actualizar_y_dibujar(pantalla, ojo_x, ojo_y, parpadeo_click):
    """
    el main.py va a llamar a esta función 60 veces por segundo 
    pasandole las coordenadas exactas de la mirada
    """
    ANCHO, ALTO = pantalla.get_size()
    fuente = pygame.font.SysFont("Arial", 24)
    
    # LOGICA DEL JUEGO
    rect_objetivo = pygame.Rect(estado.pos_objetivo[0], estado.pos_objetivo[1], 300, 300)
    
    # si el usuario mira el objetivo y parpadea
    if parpadeo_click and rect_objetivo.collidepoint(ojo_x, ojo_y):
        estado.puntuacion += 1

        estado.sonido_click.play()
        
        # mover el objetivo a otro lado
        import random
        estado.pos_objetivo = [random.randint(100, ANCHO-300), random.randint(50, ALTO-300)]

    # 2. DIBUJAR EN PANTALLA
    pantalla.fill((30, 40, 50)) # fondo del juego
    
    # dibujar objetivo
    pantalla.blit(estado.imagen_blanco, (estado.pos_objetivo[0], estado.pos_objetivo[1]))
    
    # dibujar puntuacion
    texto_puntos = fuente.render(f"Puntos: {estado.puntuacion}", True, (255, 255, 255))
    pantalla.blit(texto_puntos, (50, 50))
    
    texto_Volver = fuente.render("Presiona ESC para salir al menu", True, (200, 200, 200))
    pantalla.blit(texto_Volver, (50, 90))
    
    # dibujar el puntero del ojo del usuario adentro del juego
    pygame.draw.circle(pantalla, (0, 255, 255), (int(ojo_x), int(ojo_y)), 10)