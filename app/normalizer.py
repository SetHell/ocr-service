import re
import unicodedata
from rapidfuzz import process


ARTICULOS = ["380", "381", "382"]


def sin_tildes(txt: str):
    return "".join(
        c for c in unicodedata.normalize("NFD", txt)
        if unicodedata.category(c) != "Mn"
    )


def limpiar(txt: str):
    if txt is None:
        return ""

    txt = sin_tildes(str(txt).upper().strip())
    txt = txt.replace("°", "")
    txt = txt.replace("º", "")
    txt = txt.replace('"', "")
    txt = txt.replace("?", "")
    txt = txt.replace("¿", "")
    txt = re.sub(r"[^A-Z0-9Ñ:/.\-\s]", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def centro_y(item):
    return sum(p[1] for p in item["bbox"]) / 4


def centro_x(item):
    return sum(p[0] for p in item["bbox"]) / 4


def bbox_limites(item):
    xs = [p[0] for p in item["bbox"]]
    ys = [p[1] for p in item["bbox"]]
    return min(xs), min(ys), max(xs), max(ys)


def texto_total(textos):
    ordnds = sorted(textos, key=lambda t: (centro_y(t), centro_x(t)))
    return " ".join(limpiar(t["texto"]) for t in ordnds)


def mejor_coincidencia(valor: str, opciones: list[str], minimo=70):
    res = process.extractOne(valor, opciones) if valor else None

    if not res:
        return ""

    texto, score, _ = res
    return texto if score >= minimo else ""


def buscar_ancla(textos, palabra):
    canddts = []

    for item in textos:
        txt = limpiar(item["texto"])

        if palabra in txt:
            canddts.append(item)

    if not canddts:
        return None

    canddts.sort(key=lambda x: x["confianza"], reverse=True)
    return canddts[0]


def texto_zona(zon, nom):
    if not zon:
        return ""

    return limpiar(zon.get(nom, {}).get("texto", ""))


def normalizar_num(txt):
    txt = limpiar(txt).replace(" ", "")
    txt = txt.replace("O", "0")
    txt = txt.replace("I", "1")
    txt = txt.replace("L", "1")
    txt = txt.replace("S", "5")
    return re.sub(r"[^0-9]", "", txt)


def normalizar_letras(txt):
    txt = limpiar(txt).replace(" ", "")
    txt = txt.replace("0", "O")
    txt = txt.replace("1", "I")
    txt = txt.replace("5", "S")
    return re.sub(r"[^A-Z]", "", txt)


def extraer_nro_boleta(txt: str):
    patrones = [
        r"\bNO\s*([0-9]{5,7})\b",
        r"\bNRO\s*([0-9]{5,7})\b",
        r"\bN\s*([0-9]{5,7})\b",
        r"\b([0-9]{6})\b",
    ]

    for patron in patrones:
        m = re.search(patron, txt)
        if m:
            return m.group(1)

    return None


def extraer_hora(txt: str):
    patrones = [
        r"\b([0-2]?[0-9])[:. ]+([0-5][0-9])\b",
        r"\b([0-2][0-9])([0-5][0-9])\b",
    ]

    for patron in patrones:
        m = re.search(patron, txt)

        if m:
            h = int(m.group(1))
            mi = int(m.group(2))

            if 0 <= h <= 23 and 0 <= mi <= 59:
                return f"{h:02d}:{mi:02d}"

    return None


def extraer_dia_mes_anio(txt: str):
    m = re.search(r"\b([0-3]?[0-9])[/\-]([0-1]?[0-9])[/\-](20[0-9]{2})\b", txt)

    if m:
        dia = int(m.group(1))
        mes = int(m.group(2))
        anio = int(m.group(3))

        if 1 <= dia <= 31 and 1 <= mes <= 12:
            return f"{dia:02d}", f"{mes:02d}", str(anio)

    anio_match = re.search(r"\b(20[0-9]{2})", txt)

    return None, None, anio_match.group(1) if anio_match else None


def formar_fecha(dia, mes, anio):
    if dia and mes and anio:
        return f"{anio}-{mes}-{dia}"

    return None


def placa_valida(placa):
    if not placa:
        return False

    return bool(re.fullmatch(r"[0-9]{3,4}[A-Z]{3}", placa))


def extraer_placa_zona(zonas):
    txt = texto_zona(zonas, "placa").replace(" ", "")

    m = re.search(r"([0-9]{4}[A-Z]{3}|[0-9]{3}[A-Z]{3})", txt)
    if m:
        return m.group(1)

    nums = normalizar_num(txt)
    letras = normalizar_letras(txt)

    if len(nums) >= 4 and len(letras) >= 3:
        return nums[:4] + letras[-3:]

    if len(nums) >= 3 and len(letras) >= 3:
        return nums[:3] + letras[-3:]

    return None


def extraer_placa_general(textos):
    ancla = buscar_ancla(textos, "PLACA")

    if not ancla:
        return None

    ax1, ay1, ax2, ay2 = bbox_limites(ancla)
    cy_ancla = centro_y(ancla)

    nums = []
    letras = []

    for item in textos:
        txt = limpiar(item["texto"]).replace(" ", "")
        cx = centro_x(item)
        cy = centro_y(item)

        cerca_y = abs(cy - cy_ancla) < 85
        cerca_x = ax1 - 20 <= cx <= ax2 + 280

        if not (cerca_y and cerca_x):
            continue

        num = normalizar_num(txt)
        let = normalizar_letras(txt)

        if re.fullmatch(r"[0-9]{3,4}", num):
            nums.append((num, cx, cy))

        if re.fullmatch(r"[A-Z]{3}", let):
            if let not in ["DIA", "MES", "ANO", "NUM", "ART", "TIP", "ZON"]:
                letras.append((let, cx, cy))

    opciones = []

    for num, nx, ny in nums:
        for let, lx, ly in letras:
            mism_lin = abs(ny - ly) < 80
            derecha = 0 < lx - nx < 260

            if mism_lin and derecha:
                placa = num + let

                if placa_valida(placa):
                    opciones.append((placa, abs(ny - ly), lx - nx))

    if opciones:
        opciones.sort(key=lambda x: (x[1], x[2]))
        return opciones[0][0]

    return None


def extraer_placa(textos, zonas):
    plac_zon = extraer_placa_zona(zonas)
    plac_genrl = extraer_placa_general(textos)

    return plac_zon or plac_genrl


def extraer_no_porta(txt: str):
    claves = [
        "NO PORTA",
        "NO POR",
        "NO PORLC",
        "NO PORTC",
        "NO PORTE",
        "SIN LICENCIA",
    ]

    return any(clave in txt for clave in claves)


def extraer_licencia(txt: str):
    if extraer_no_porta(txt):
        return None

    m = re.search(r"LICENCIA\s*N?\s*([0-9]{4,12})", txt)

    if m:
        return m.group(1)

    return None


def extraer_nombre_conductor(textos):
    ancla = buscar_ancla(textos, "NOMBRE DEL CONDUCTOR")

    if not ancla:
        return None

    ax1, ay1, ax2, ay2 = bbox_limites(ancla)
    cy_ancla = centro_y(ancla)

    canddts = []

    for item in textos:
        txt = limpiar(item["texto"])
        cx = centro_x(item)
        cy = centro_y(item)

        if abs(cy - cy_ancla) < 70 and cx > ax2 and len(txt) > 2:
            if txt not in ["DATOS DEL VEHICULO", "TIPO", "MARCA", "COLOR"]:
                canddts.append((txt, cx))

    if not canddts:
        return None

    canddts.sort(key=lambda x: x[1])
    nom = " ".join(x[0] for x in canddts)

    return nom if len(nom) >= 5 else None


def extraer_articulo_texto(txt: str):
    encntrds = re.findall(r"\b(38[0-9]|39[0-9])\b", txt)

    for valor in encntrds:
        mejor = mejor_coincidencia(valor, ARTICULOS, minimo=60)

        if mejor:
            return f"ART {mejor}"

    return None


def extraer_articulo_zona(zonas):
    txt = texto_zona(zonas, "art")
    nums = normalizar_num(txt)

    if not nums:
        return None

    if len(nums) >= 3:
        mejor = mejor_coincidencia(nums[:3], ARTICULOS, minimo=55)
        return f"ART {mejor}" if mejor else None

    return None


def articulo_valido(art):
    return art in ["ART 380", "ART 381", "ART 382"]


def extraer_num_texto(txt: str):
    m = re.search(r"\bNUM[:\s]*([0-9]{1,3})\b", txt)

    if m:
        return m.group(1)

    return None


def extraer_num_zona(zonas):
    txt = texto_zona(zonas, "num")
    nums = normalizar_num(txt)

    if nums:
        return nums[:3]

    return None


def num_valido(num):
    return bool(num and re.fullmatch(r"[0-9]{1,3}", num))


def limpiar_lugar_basura(txt):
    basura = [
        "SENOR",
        "CONDUCTOR",
        "PARTIR",
        "PAGO",
        "INFRACCION",
        "ENTIDADES",
        "FINANCIERAS",
        "GRACIAS",
        "CONTRIBUIR",
        "SIGUIENTES",
        "HORAS",
        "UNICAMENTE",
        "BANCOS",
    ]

    return any(b in txt for b in basura)


def normalizar_lugar(zonas):
    txt = texto_zona(zonas, "lugar")

    if not txt:
        return None

    if limpiar_lugar_basura(txt):
        return txt

    if "AV" in txt and ("MARISCAL" in txt or "SANT" in txt or "SF" in txt):
        return "AV. MARISCAL SANT"

    return txt


def normalizar_zona(zonas):
    txt = texto_zona(zonas, "zona")

    if not txt:
        return None

    if limpiar_lugar_basura(txt):
        return txt

    if "CENT" in txt or txt in ["C", "CEN", "CENT"]:
        return "CENTRAL"

    return txt


def dato_revisar_por_basura(valor):
    if not valor:
        return True

    return limpiar_lugar_basura(valor)


def normalizar_respuesta(textos, caslls, zonas=None):
    txt = texto_total(textos)
    zonas = zonas or {}

    dia, mes, anio = extraer_dia_mes_anio(txt)

    placa = extraer_placa(textos, zonas)
    art = extraer_articulo_zona(zonas) or extraer_articulo_texto(txt)
    nro_infr = extraer_num_zona(zonas) or extraer_num_texto(txt)

    lugar = normalizar_lugar(zonas)
    zona = normalizar_zona(zonas)

    datos = {
        "hora": extraer_hora(txt),
        "dia": dia,
        "mes": mes,
        "anio": anio,
        "fecha": formar_fecha(dia, mes, anio),

        "placa": placa,
        "nro_lic": extraer_licencia(txt),
        "nom_conductor": extraer_nombre_conductor(textos),

        "tip_vehi": caslls.get("tip_vehi", {}).get("detectado"),
        "marca": caslls.get("marca", {}).get("detectado"),
        "color": caslls.get("color", {}).get("detectado"),

        "art": art,
        "nro_infr": nro_infr,

        "lugar": lugar,
        "zona": zona,
        "observ": None,

        "nro_boleta": extraer_nro_boleta(txt),
    }

    camps_rev = []

    if not datos["hora"]:
        camps_rev.append("HORA")

    if not datos["dia"]:
        camps_rev.append("DÍA")

    if not datos["mes"]:
        camps_rev.append("MES")

    if not datos["anio"]:
        camps_rev.append("AÑO")

    if not placa_valida(datos["placa"]):
        camps_rev.append("PLACA")

    if not datos["tip_vehi"]:
        camps_rev.append("TIPO VEHÍCULO")

    if not datos["marca"]:
        camps_rev.append("MARCA")

    if not datos["color"]:
        camps_rev.append("COLOR")

    if not articulo_valido(datos["art"]):
        camps_rev.append("ARTÍCULO")

    if not num_valido(datos["nro_infr"]):
        camps_rev.append("NÚMERO INFRACCIÓN")

    if dato_revisar_por_basura(datos["lugar"]):
        camps_rev.append("LUGAR")

    if dato_revisar_por_basura(datos["zona"]):
        camps_rev.append("ZONA")

    datos["campos_revisar"] = camps_rev

    return datos