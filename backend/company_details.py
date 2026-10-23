"""Campos cadastrais equivalentes ao RotaFY, sem plano de uso."""
import re

import phonenumbers
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator

from backend.documents import company_document

STATES = set('AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split())
DETAIL_FIELDS = ('corporate_name', 'cnpj', 'contact_phone', 'address', 'address_number',
                 'address_complement', 'neighborhood', 'city', 'state', 'postal_code', 'operational_profile')


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class InitialAdmin(Input):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr = Field(max_length=254)
    password: SecretStr = Field(min_length=12, max_length=128)

    @field_validator('password')
    @classmethod
    def valid_password(cls, value):
        raw = value.get_secret_value()
        if not any(char.isupper() for char in raw) or not any(not char.isalnum() and not char.isspace() for char in raw):
            raise ValueError('Use pelo menos 12 caracteres, uma letra maiúscula e um caractere especial.')
        return value


class CompanyDetails(Input):
    trade_name: str = Field(min_length=2, max_length=150)
    corporate_name: str = Field(min_length=2, max_length=150)
    cnpj: str = Field(min_length=11, max_length=30)
    contact_phone: str = Field(min_length=1, max_length=50)
    address: str = Field(min_length=2, max_length=250)
    address_number: str = Field(min_length=1, max_length=30)
    address_complement: str = Field(default='', max_length=150)
    neighborhood: str = Field(min_length=2, max_length=100)
    city: str = Field(min_length=2, max_length=100)
    state: str = Field(min_length=2, max_length=2)
    postal_code: str = Field(min_length=8, max_length=9)
    operational_profile: str = Field(pattern=r'^(office|industrial|logistics|mixed)$')

    @field_validator('cnpj')
    @classmethod
    def valid_document(cls, value):
        return company_document(value)

    @field_validator('contact_phone')
    @classmethod
    def valid_phone(cls, value):
        try:
            number = phonenumbers.parse(value, 'BR')
        except phonenumbers.NumberParseException:
            raise ValueError('Informe telefone válido com DDD ou + e código do país.') from None
        if not phonenumbers.is_valid_number(number) or number.extension:
            raise ValueError('Informe telefone válido, sem ramal.')
        return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)

    @field_validator('state')
    @classmethod
    def valid_state(cls, value):
        value = value.upper()
        if value not in STATES:
            raise ValueError('Informe uma UF brasileira válida.')
        return value

    @field_validator('postal_code')
    @classmethod
    def valid_postal_code(cls, value):
        value = value.replace('-', '')
        if not re.fullmatch(r'[0-9]{8}', value):
            raise ValueError('Informe o CEP com oito dígitos.')
        return value


class CompanyCreate(CompanyDetails):
    slug: str = Field(min_length=2, max_length=50, pattern=r'^[a-z0-9]+$')
    admin: InitialAdmin


class CompanyUpdate(CompanyDetails):
    slug: str = Field(min_length=2, max_length=60, pattern=r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
    is_active: bool = Field(strict=True)
    expected_version: int = Field(ge=1, strict=True)


def company_public(row, details=True):
    fields = ('id','name','slug','version','created_at') + (DETAIL_FIELDS if details else ())
    return {key: row[key] for key in fields} | {'trade_name': row['name'], 'is_active': bool(row['is_active'])}
