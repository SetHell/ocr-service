from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from app.easy_ocr import leer_imagen
import traceback

app = FastAPI(
    title="Servicio OCR EasyOCR",
    description="Servicio BETA para auto llenado de boletas con EasyOCR",
    version="0.1.0",
)

@app.get("/")
def inicio():
    return {
        "mensaje": "Servicio OCR funcionando",
        "motor": "EasyOCR",
        "estado": "BETA",
    }

@app.post("/ocr/procesar")
async def procesar_ocr(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Debe subir una imagen")

    contenido = await file.read()

    try:
        return JSONResponse(content=leer_imagen(contenido))
    except Exception as e:
        print("ERROR OCR:")
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"No se pudo procesar la imagen: {str(e)}",
        )