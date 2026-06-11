import cv2
import numpy as np
from rapidfuzz import process


TIPOS = ["AUTOMÓVIL", "MINIBÚS", "VAGONETA", "CAMIONETA", "MICROBÚS"]
MARCAS = ["TOYOTA", "NISSAN", "VOLKSWAGEN", "SUZUKI", "MITSUBISHI"]
COLORES = ["BLANCO", "ROJO", "NEGRO", "AZUL"]


def limpiar(txt: str):
    return (
        str(txt)
        .upper()
        .replace("Á", "A")
        .replace("É", "E")
        .replace("Í", "I")
        .replace("Ó", "O")
        .replace("Ú", "U")
        .replace(":", "")
        .strip()
    )


def obtener_bbox(item):
    xs = [p[0] for p in item["bbox"]]
    ys = [p[1] for p in item["bbox"]]
    return int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))


def centro_x(item):
    x1, y1, x2, y2 = obtener_bbox(item)
    return (x1 + x2) / 2


def centro_y(item):
    x1, y1, x2, y2 = obtener_bbox(item)
    return (y1 + y2) / 2


def buscar_texto_opcion(textos, opcion):
    canddts = []
    opc = limpiar(opcion)

    for item in textos:
        txt = limpiar(item["texto"])

        if opc in txt:
            canddts.append(item)
            continue

        res = process.extractOne(txt, [opc])

        if res and res[1] >= 82:
            canddts.append(item)

    if not canddts:
        return None

    canddts.sort(key=lambda x: x["confianza"], reverse=True)
    return canddts[0]


def medir_region(img, x1, y1, x2, y2):
    x1 = max(0, int(x1))
    y1 = max(0, int(y1))
    x2 = min(img.shape[1], int(x2))
    y2 = min(img.shape[0], int(y2))

    reg = img[y1:y2, x1:x2]

    if reg.size == 0:
        return 0.0

    gris = cv2.cvtColor(reg, cv2.COLOR_BGR2GRAY)
    gris = cv2.GaussianBlur(gris, (3, 3), 0)

    _, binaria = cv2.threshold(gris, 135, 255, cv2.THRESH_BINARY_INV)

    pixeles = np.count_nonzero(binaria)
    total = binaria.shape[0] * binaria.shape[1]

    return round(float(pixeles / total), 4)


def medir_marca(img, item, opcion):
    x1, y1, x2, y2 = obtener_bbox(item)
    alto = max(y2 - y1, 20)

    txt = limpiar(item["texto"])
    opc = limpiar(opcion)

    if "TIPO" in txt and opc in txt:
        return medir_region(img, x1 + 55, y1 - 5, x1 + 95, y1 + alto + 5)

    return medir_region(img, x1 - 45, y1 - 5, x1 - 8, y1 + alto + 5)


def buscar_otro(textos, grup):
    otros = []

    for item in textos:
        txt = limpiar(item["texto"])

        if "OTRO" not in txt:
            continue

        cx = centro_x(item)

        if grup == "tipo" and cx < 300:
            otros.append(item)

        if grup == "marca" and 300 <= cx < 600:
            otros.append(item)

        if grup == "color" and cx >= 580:
            otros.append(item)

    if not otros:
        return None

    otros.sort(key=lambda x: centro_y(x))
    otro = otros[0]

    ox1, oy1, ox2, oy2 = obtener_bbox(otro)
    oy = centro_y(otro)

    canddts = []

    for item in textos:
        txt = limpiar(item["texto"])

        if not txt or "OTRO" in txt:
            continue

        cx = centro_x(item)
        cy = centro_y(item)

        mism_lin = abs(cy - oy) < 45
        der = ox2 < cx < ox2 + 220

        if mism_lin and der:
            if txt not in ["TIPO", "MARCA", "COLOR", "NUM", "ZONA"]:
                canddts.append((txt, cx))

    if not canddts:
        return None

    canddts.sort(key=lambda x: x[1])
    valor = " ".join(c[0] for c in canddts).strip()

    return valor if valor else None


def detectar_grupo(img, textos, opciones, grupo):
    results = {}
    mej_opcion = None
    mej_score = 0.0

    for opcion in opciones:
        item = buscar_texto_opcion(textos, opcion)

        if not item:
            results[opcion] = {
                "marcado": False,
                "score": 0,
                "encontrado": False,
            }
            continue

        score = medir_marca(img, item, opcion)

        results[opcion] = {
            "marcado": False,
            "score": score,
            "encontrado": True,
        }

        if score > mej_score:
            mej_score = score
            mej_opcion = opcion

    if mej_opcion and mej_score >= 0.10:
        results[mej_opcion]["marcado"] = True
        return mej_opcion, results, None

    otro_valor = buscar_otro(textos, grupo)

    if otro_valor:
        results["OTRO"] = {
            "marcado": True,
            "score": 0,
            "encontrado": True,
            "valor": otro_valor,
        }

        return otro_valor, results, otro_valor

    results["OTRO"] = {
        "marcado": False,
        "score": 0,
        "encontrado": False,
        "valor": None,
    }

    return None, results, None


def detc_cas(img, textos):
    tip_detect, tip_result, otro_tipo = detectar_grupo(img, textos, TIPOS, "tipo")
    marc_detect, marc_result, otro_marca = detectar_grupo(img, textos, MARCAS, "marca")
    color_detect, color_result, otro_color = detectar_grupo(img, textos, COLORES, "color")

    return {
        "tip_vehi": {
            "detectado": tip_detect,
            "otro": otro_tipo,
            "opciones": tip_result,
        },
        "marca": {
            "detectado": marc_detect,
            "otro": otro_marca,
            "opciones": marc_result,
        },
        "color": {
            "detectado": color_detect,
            "otro": otro_color,
            "opciones": color_result,
        },
        "nota": "Detección BETA por densidad de marca. Si ninguna casilla está marcada, intenta leer OTRO.",
    }