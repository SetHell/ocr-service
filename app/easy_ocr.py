import easyocr
import numpy as np
import cv2

from app.normalizer import normalizar_respuesta
from app.checkbox_detector import detc_cas

reader = easyocr.Reader(["es"], gpu=False)


def limpiar_bbox(bbox):
    return [[float(punt[0]), float(punt[1])] for punt in bbox]


def bytes_a_imagen(cont: bytes):
    arr = np.frombuffer(cont, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    if img is None:
        raise ValueError("Imagen inválida o no se pudo leer")

    return img


def recortar(img, x1, y1, x2, y2):
    h, w = img.shape[:2]
    return img[int(h * y1):int(h * y2), int(w * x1):int(w * x2)]


def mejorar_zona(zona):
    gris = cv2.cvtColor(zona, cv2.COLOR_BGR2GRAY)
    gris = cv2.resize(gris, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    gris = cv2.GaussianBlur(gris, (3, 3), 0)
    gris = cv2.equalizeHist(gris)
    return gris


def leer_zona(img, coords, allowlist=None):
    zona = recortar(img, *coords)
    zona = mejorar_zona(zona)

    args = {
        "detail": 1,
        "paragraph": False,
    }

    if allowlist:
        args["allowlist"] = allowlist

    result = reader.readtext(zona, **args)

    textos = []

    for bbox, texto, conf in result:
        textos.append({
            "texto": str(texto),
            "confianza": round(float(conf), 4),
            "bbox": limpiar_bbox(bbox),
        })

    return {
        "texto": " ".join([t["texto"] for t in textos]),
        "items": textos,
    }


def leer_zonas(img):
    return {
        "placa": leer_zona(
            img,
            (0.22, 0.25, 0.50, 0.34),
            "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        ),
        "art": leer_zona(
            img,
            (0.42, 0.50, 0.56, 0.57),
            "0123456789",
        ),
        "num": leer_zona(
            img,
            (0.70, 0.50, 0.87, 0.57),
            "0123456789",
        ),
        "lugar": leer_zona(
            img,
            (0.32, 0.53, 0.66, 0.61),
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 ._-",
        ),
        "zona": leer_zona(
            img,
            (0.62, 0.53, 0.92, 0.61),
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 ._-",
        ),
    }


def leer_imagen(contenido: bytes):
    img = bytes_a_imagen(contenido)
    result = reader.readtext(img)

    textos = []

    for bbox, texto, conf in result:
        textos.append({
            "texto": str(texto),
            "confianza": round(float(conf), 4),
            "bbox": limpiar_bbox(bbox),
        })

    zonas = leer_zonas(img)
    caslls = detc_cas(img, textos)
    dats_sugs = normalizar_respuesta(textos, caslls, zonas)

    return {
        "mensaje": "Imagen procesada con EasyOCR",
        "cantidad_textos": len(textos),
        "texto_bruto": textos,
        "zonas": zonas,
        "casillas": caslls,
        "datos_sugeridos": dats_sugs,
        "advertencia": "Los datos son sugerencias. El usuario debe revisarlos antes de registrar.",
    }