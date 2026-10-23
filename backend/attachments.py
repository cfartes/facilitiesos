"""Somente imagens decodificadas e regravadas; originais não são persistidos."""
from io import BytesIO
from pathlib import PurePath
from urllib.parse import unquote
import hashlib
import unicodedata
import warnings
from threading import BoundedSemaphore

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 16_000_000
MAX_PER_RECORD = 10
MAX_COMPANY_BYTES = 200 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = MAX_PIXELS
processing_slots = BoundedSemaphore(2)


def normalize_image(raw, encoded_name, content_type):
    if not processing_slots.acquire(blocking=False):
        raise HTTPException(429, 'Há imagens em processamento. Aguarde alguns segundos e tente novamente.', headers={'Retry-After': '5'})
    try:
        return _normalize_image(raw, encoded_name, content_type)
    finally:
        processing_slots.release()


def _normalize_image(raw, encoded_name, content_type):
    if not raw or len(raw) > MAX_BYTES:
        raise HTTPException(413, 'Envie uma imagem de até 5 MiB.')
    try:
        name = unicodedata.normalize('NFC', unquote(encoded_name, errors='strict')).strip()
    except UnicodeDecodeError:
        raise HTTPException(422, 'O nome do arquivo não é válido. Renomeie a imagem e tente novamente.') from None
    if (not name or len(name) > 120 or '/' in name or '\\' in name
            or any(unicodedata.category(char).startswith('C') for char in name)):
        raise HTTPException(422, 'Use um nome de arquivo com até 120 caracteres, sem caminhos ou caracteres de controle.')
    suffix = PurePath(name).suffix.lower()
    expected = {'image/jpeg': ('JPEG', {'.jpg', '.jpeg'}), 'image/png': ('PNG', {'.png'})}.get(content_type)
    if not expected or suffix not in expected[1]:
        raise HTTPException(415, 'Envie somente fotos JPEG ou PNG. Outros formatos não são aceitos nesta etapa.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw), formats=['JPEG', 'PNG']) as source:
                if source.format != expected[0] or source.width * source.height > MAX_PIXELS or getattr(source, 'n_frames', 1) != 1:
                    raise ValueError('unsupported image')
                source.verify()
            with Image.open(BytesIO(raw), formats=['JPEG', 'PNG']) as source:
                source.load()
                oriented = ImageOps.exif_transpose(source)
                mode = 'RGBA' if source.format == 'PNG' and ('A' in oriented.getbands() or 'transparency' in oriented.info) else 'RGB'
                converted = oriented.convert(mode)
                # Uma nova imagem conserva apenas os pixels, sem EXIF, GPS, comentários ou ICC.
                clean = Image.new(mode, converted.size)
                clean.paste(converted)
                output = BytesIO()
                clean.save(output, format=expected[0], **({'quality': 90} if expected[0] == 'JPEG' else {}))
                normalized = output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(422, 'Imagem inválida, animada, danificada ou acima de 16 megapixels. Exporte uma foto JPEG/PNG e tente novamente.') from None
    if len(normalized) > MAX_BYTES:
        raise HTTPException(413, 'A imagem processada ultrapassa 5 MiB. Reduza suas dimensões e tente novamente.')
    return name, normalized, hashlib.sha256(normalized).hexdigest()
