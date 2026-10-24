"""Etiquetas locais; o identificador do equipamento nunca concede acesso ao painel."""
import base64
from io import BytesIO
from urllib.parse import urlencode
from uuid import UUID

import qrcode
from pydantic import BaseModel, ConfigDict, Field


class LabelInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    asset_ids: list[UUID] = Field(min_length=1, max_length=1000)
    phone: str = Field(pattern=r'^[1-9][0-9]{7,14}$')


def equipment(db, company, identifier):
    asset = db.execute("SELECT * FROM assets WHERE company_id=:company AND id=:id AND status<>'retired'", {'company': company, 'id': str(identifier)}).fetchone()
    if not asset:
        return None
    names, seen, parent = [], set(), asset['location_id']
    while parent and parent not in seen and len(seen) < 5:
        row = db.execute('SELECT * FROM locations WHERE company_id=:company AND id=:id AND unit_id=:unit AND is_active=1', {'company': company, 'id': parent, 'unit': asset['unit_id']}).fetchone()
        if not row:
            return None
        seen.add(parent); names.insert(0, row['name']); parent = row['parent_id']
    if parent or row['id'] != asset['unit_id'] or row['kind'] != 'unit':
        return None
    return {'unit': {'id': row['id'], 'label': row['name']},
            'place': {'id': asset['location_id'], 'label': ' / '.join(names)},
            'asset': {'id': asset['id'], 'label': asset['code'] + ' — ' + asset['name']}, 'record': asset}


def label(selection, phone):
    asset = selection['record']
    url = 'https://wa.me/' + phone + '?' + urlencode({'text': 'EQUIPAMENTO ' + asset['id']})
    output = BytesIO()
    qrcode.make(url, box_size=6, border=4).save(output, format='PNG')
    return {'id': asset['id'], 'code': asset['code'], 'name': asset['name'], 'location': selection['place']['label'],
            'url': url, 'qr_code': 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode()}
