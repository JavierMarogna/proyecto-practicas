import pygame
import sys
import random
import os
import math

pygame.init()

def resolver_ruta_local(archivo_recurso):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(os.path.dirname(__file__), archivo_recurso)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), archivo_recurso)

# CONSTANTES
TAMAÑO_FILAS = 5
TAMAÑO_COLUMNAS = 5
TAMAÑO_CASILLA = 100
MARGEN = 10

GRIS_FONDO = (40, 40, 40)
GRIS_CASILLA = (60, 60, 60)
BLANCO = (255, 255, 255)
FONT = pygame.font.SysFont("Arial", 30)

# MEDIDAS DEL TABLERO
ANCHO_TABLERO = TAMAÑO_COLUMNAS * TAMAÑO_CASILLA + (TAMAÑO_COLUMNAS + 1) * MARGEN
ALTO_TABLERO = TAMAÑO_FILAS * TAMAÑO_CASILLA + (TAMAÑO_FILAS + 1) * MARGEN

# CARGAR IMAGENES
IMAGENES_NIVEL = {}
NIVEL_MAXIMO_IMAGEN = 10

def iniciar(pantalla, juego_vuelve_al_menu):
    for nivel in range(1, NIVEL_MAXIMO_IMAGEN + 1):
        ruta_imagen = resolver_ruta_local(f"pieza_{nivel}.png")
        if os.path.exists(ruta_imagen):
            img = pygame.image.load(ruta_imagen).convert_alpha()
            IMAGENES_NIVEL[nivel] = pygame.transform.scale(img, (TAMAÑO_CASILLA, TAMAÑO_CASILLA))
        else:
            surf = pygame.Surface((TAMAÑO_CASILLA, TAMAÑO_CASILLA))
            surf.fill((200, 0, 0))
            surf.blit(FONT.render(str(nivel), True, (255,255,255)))
            IMAGENES_NIVEL[nivel] = surf

# CLASE PARA ANIMAR LAS PIEZAS
class PiezaAnimada:
    def __init__(self, nivel, fila, columna, offset_x=0, offset_y=0):
        self.nivel = nivel
        self.fila = fila
        self.columna = columna
        
        # posición real en píxeles sumando el offset de centrado
        self.x = offset_x + MARGEN + columna * (TAMAÑO_CASILLA + MARGEN)
        self.y = offset_y + MARGEN + fila * (TAMAÑO_CASILLA + MARGEN)
        
        self.target_x = self.x
        self.target_y = self.y
        self.en_movimiento = False
        self.destruir_al_llegar = False

    def mover_a(self, fila_destino, columna_destino, offset_x=0, offset_y=0, destruir=True):
        """asigna un nuevo destino en píxeles a la pieza considerando el centrado"""
        self.target_x = offset_x + MARGEN + columna_destino * (TAMAÑO_CASILLA + MARGEN)
        self.target_y = offset_y + MARGEN + fila_destino * (TAMAÑO_CASILLA + MARGEN)
        self.en_movimiento = True
        self.destruir_al_llegar = destruir

    def actualizar(self, velocidad=15):
        if not self.en_movimiento:
            return True

        dx = self.target_x - self.x
        dy = self.target_y - self.y
        distancia = math.hypot(dx, dy)

        if distancia <= velocidad:
            self.x = self.target_x
            self.y = self.target_y
            self.en_movimiento = False
            return True
        else:
            self.x += (dx / distancia) * velocidad
            self.y += (dy / distancia) * velocidad
            return False

    def dibujar(self, superficie):
        nivel_img = min(self.nivel, NIVEL_MAXIMO_IMAGEN)
        superficie.blit(IMAGENES_NIVEL[nivel_img], (int(self.x), int(self.y)))


class EstadoJuego:
    tablero = [[0 for _ in range(TAMAÑO_COLUMNAS)] for _ in range(TAMAÑO_FILAS)]
    piezas_activas = []       
    piezas_en_fusion = []     
    pieza_siguiente = 1
    bloquear_interfaz = False 

    # lista de posibles piezas a salir
    posibles_piezas = [1, 1, 1]

    offset_x = 0
    offset_y = 0

estado = EstadoJuego()

def generar_siguiente_pieza():
    # elije la siguiente pieza aleatoriamente
    return random.choice(estado.posibles_piezas)

def obtener_vecinos_identicos(r, c, valor, visitados):
    if (r, c) in visitados: return []
    visitados.add((r, c))
    coordenadas_grupo = [(r, c)]
    direcciones = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    for dr, dc in direcciones:
        nr, nc = r + dr, c + dc
        if 0 <= nr < TAMAÑO_FILAS and 0 <= nc < TAMAÑO_COLUMNAS:
            if estado.tablero[nr][nc] == valor:
                coordenadas_grupo.extend(obtener_vecinos_identicos(nr, nc, valor, visitados))
    return coordenadas_grupo

def verificar_fusiones_en_tablero(r_centro, c_centro):
    valor_actual = estado.tablero[r_centro][c_centro]
    if valor_actual == 0: return False

    visitados = set()
    grupo = obtener_vecinos_identicos(r_centro, c_centro, valor_actual, visitados)

    if len(grupo) >= 3:
        estado.bloquear_interfaz = True 
        
        for r, c in grupo:
            if r == r_centro and c == c_centro:
                continue 
            
            pieza_vecina = next((p for p in estado.piezas_activas if p.fila == r and p.columna == c), None)
            if pieza_vecina:
                estado.piezas_activas.remove(pieza_vecina)
                # se pasan los offsets actuales para que viajen al punto centrado correcto
                pieza_vecina.mover_a(r_centro, c_centro, estado.offset_x, estado.offset_y, destruir=True)
                estado.piezas_en_fusion.append(pieza_vecina)
            
            estado.tablero[r][c] = 0 
            
        nuevo_valor = valor_actual + 1
        estado.tablero[r_centro][c_centro] = nuevo_valor

        estado.posibles_piezas.append(nuevo_valor)

        return True
        
    return False

def procesar_jugada(fila, columna):
    if estado.tablero[fila][columna] != 0: return

    estado.tablero[fila][columna] = estado.pieza_siguiente
    nueva_pieza = PiezaAnimada(estado.pieza_siguiente, fila, columna, estado.offset_x, estado.offset_y)
    estado.piezas_activas.append(nueva_pieza)

    verificar_fusiones_en_tablero(fila, columna)
    
    if not estado.bloquear_interfaz:
        estado.pieza_siguiente = generar_siguiente_pieza()

def actualizar_y_dibujar(pantalla, ojo_x, ojo_y, parpadeo_click):
    ANCHO_PANTALLA, ALTO_PANTALLA = pantalla.get_size()
    pantalla.fill(GRIS_FONDO)
    
    estado.offset_x = (ANCHO_PANTALLA - ANCHO_TABLERO) // 2 + 120
    estado.offset_y = (ALTO_PANTALLA - ALTO_TABLERO) // 2
    
    if parpadeo_click and not estado.bloquear_interfaz:
        pos_x = ojo_x - estado.offset_x
        pos_y = ojo_y - estado.offset_y
        
        # verifica que el clic esté dentro del tablero centrado antes de procesar
        if pos_x >= 0 and pos_y >= 0:
            columna = pos_x // (TAMAÑO_CASILLA + MARGEN)
            fila = pos_y // (TAMAÑO_CASILLA + MARGEN)
            if fila < TAMAÑO_FILAS and columna < TAMAÑO_COLUMNAS:
                procesar_jugada(int(fila), int(columna))

    # actualiza la animacion de fusion de la piezas
    if estado.piezas_en_fusion:
        for p in estado.piezas_en_fusion[:]:
            llego = p.actualizar(velocidad=18) 
            if llego:
                estado.piezas_en_fusion.remove(p)
        
        if len(estado.piezas_en_fusion) == 0:
            # quita el offset antes de calcular la fila/columna destino de la animación
            r_centro = (p.target_y - estado.offset_y) // (TAMAÑO_CASILLA + MARGEN)
            c_centro = (p.target_x - estado.offset_x) // (TAMAÑO_CASILLA + MARGEN)
            
            pieza_centro = next((p for p in estado.piezas_activas if p.fila == r_centro and p.columna == c_centro), None)
            if pieza_centro:
                pieza_centro.nivel = estado.tablero[r_centro][c_centro]
            
            otra_fusion = verificar_fusiones_en_tablero(r_centro, c_centro)
            if not otra_fusion:
                estado.bloquear_interfaz = False
                estado.pieza_siguiente = generar_siguiente_pieza()

    # dibujar escenario
    # 1. rejilla de fondo
    for fila in range(TAMAÑO_FILAS):
        for columna in range(TAMAÑO_COLUMNAS):
            x = estado.offset_x + MARGEN + columna * (TAMAÑO_CASILLA + MARGEN)
            y = estado.offset_y + MARGEN + fila * (TAMAÑO_CASILLA + MARGEN)
            pygame.draw.rect(pantalla, GRIS_CASILLA, (x, y, TAMAÑO_CASILLA, TAMAÑO_CASILLA), border_radius=5)

    # 2. piezas colocadas
    for pieza in estado.piezas_activas:
        pieza.dibujar(pantalla)

    # 3. piezas que se estan moviendo
    for pieza in estado.piezas_en_fusion:
        pieza.dibujar(pantalla)

    texto_sig = FONT.render("Próxima:", True, BLANCO)
    
    pantalla.blit(texto_sig, (estado.offset_x -200 + MARGEN, 95))
    
    nivel_sig_imagen = min(estado.pieza_siguiente, NIVEL_MAXIMO_IMAGEN)
    img_interfaz = pygame.transform.scale(IMAGENES_NIVEL[nivel_sig_imagen], (70, 70))
    pantalla.blit(img_interfaz, (estado.offset_x - 70, 100))

    pygame.draw.circle(pantalla, (0, 255, 255), (int(ojo_x), int(ojo_y)), 10)