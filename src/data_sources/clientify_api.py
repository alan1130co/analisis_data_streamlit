"""
Cliente para la API de Clientify.

TODO: completar la implementación cuando se conecte la API.
Documentación: https://api.clientify.net/v1/docs/
"""
import requests
import pandas as pd

from .base import ContactsDataSource
from src.config.settings import CLIENTIFY_API_TOKEN, CLIENTIFY_BASE_URL


class ClientifyAPIClient(ContactsDataSource):
    """Cliente HTTP que carga contactos directamente desde la API de Clientify."""

    def __init__(self, token: str = CLIENTIFY_API_TOKEN, base_url: str = CLIENTIFY_BASE_URL):
        if not token:
            raise ValueError(
                "CLIENTIFY_API_TOKEN no configurado. "
                "Definilo en .env o pasalo al constructor."
            )
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Token {self.token}",
            "Content-Type": "application/json",
        })

    @property
    def source_name(self) -> str:
        return "API Clientify"

    def load(self) -> pd.DataFrame:
        """
        Pagina por todos los contactos y los devuelve como DataFrame.
        TODO: ajustar el endpoint y el manejo de paginación al de Clientify.
        """
        contacts = []
        url = f"{self.base_url}/contacts/"
        while url:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
            contacts.extend(payload.get("results", []))
            url = payload.get("next")  # Clientify usa paginación tipo DRF

        df = pd.DataFrame(contacts)
        # TODO: mapear los campos de la API al mismo esquema que el Excel
        return df
