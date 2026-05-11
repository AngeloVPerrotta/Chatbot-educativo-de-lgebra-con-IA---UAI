import mercadopago
import os
import logging

logger = logging.getLogger(__name__)

PLAN_CONFIG = {
    'basico':     {'title': 'AlgorIA - 15 consultas extra',  'unit_price': 500,  'qty': 15},
    'estudiante': {'title': 'AlgorIA - 60 consultas extra',  'unit_price': 1500, 'qty': 60},
    'intensivo':  {'title': 'AlgorIA - 200 consultas extra', 'unit_price': 3500, 'qty': 200},
    'apoyo':      {'title': 'AlgorIA - Apoyo al proyecto',   'unit_price': 1000, 'qty': 25},
}


def create_payment_link(user_email: str, plan: str = 'apoyo') -> str:
    token = os.getenv("MP_ACCESS_TOKEN", "")
    if not token:
        logger.error("MP_ACCESS_TOKEN no está configurado")
        raise ValueError("MP_ACCESS_TOKEN no configurado. Contactá al administrador.")

    sdk = mercadopago.SDK(token)
    config = PLAN_CONFIG.get(plan, PLAN_CONFIG['apoyo'])

    preference_data = {
        "items": [{
            "title": config['title'],
            "quantity": 1,
            "unit_price": config['unit_price'],
            "currency_id": "ARS",
        }],
        "external_reference": f"{plan}|{user_email}",
        "back_urls": {
            "success": "https://algoria.angeloperrotta.online/?payment=success",
            "failure": "https://algoria.angeloperrotta.online/?payment=failure",
        },
        "auto_return": "approved",
        "notification_url": "https://chatbot-educativo-de-lgebra-con-ia-uai-production.up.railway.app/payment/webhook",
    }
    result = sdk.preference().create(preference_data)
    return result["response"]["init_point"]
