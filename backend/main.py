from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv
import os
import logging
import traceback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from agents.algebra_agent import chat as algebra_chat
from agents.calculo_agent import chat as calculo_chat
from utils.session_manager import get_session, append_message, get_messages, clear_session
from utils.analytics import (
    get_stats,
    get_recent_interactions,
    get_or_create_user,
    get_user_by_email,
    add_tokens_used,
    check_token_limit,
    get_all_users,
    save_feedback,
    get_feedback_stats,
    get_recent_feedback,
    save_chat_message,
    get_user_sessions,
    get_session_messages,
    set_user_role,
    is_admin_or_super,
    is_superadmin,
    check_rate_limit,
    increment_rate_limit,
    grant_extra_messages,
    get_user_payment_status,
    save_error_report,
    get_error_reports,
    update_report_status,
)
from utils.payments import create_payment_link

load_dotenv(override=False)
logger.info(f'GEMINI_API_KEY presente en env: {"Si" if os.getenv("GEMINI_API_KEY") else "No"}')

app = FastAPI(title="AlgorIA API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        'https://algoria.angeloperrotta.online',
        'http://localhost:5500',
        'http://127.0.0.1:5500'
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Modelos de validación ---

class ChatRequest(BaseModel):
    message: str
    materia: str = "algebra"
    session_id: str
    user_email: Optional[str] = None
    device_fp: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str

class AuthRequest(BaseModel):
    email: str
    name: Optional[str] = None

class AdminVerifyRequest(BaseModel):
    email: str
    pin: str

class FeedbackRequest(BaseModel):
    user_email: str
    rating: int
    message: Optional[str] = None

class SetRoleRequest(BaseModel):
    target_email: str
    role: str

class ErrorReportRequest(BaseModel):
    description: str
    page: str
    user_email: Optional[str] = None


# --- Endpoints base ---

@app.get("/")
def read_root():
    return {"message": "AlgorIA API is running"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


# --- POST /auth ---
# Si el email existe → devuelve el user (name ignorado).
# Si no existe y viene name → crea y devuelve el user.
# Si no existe y no viene name → 404 con {exists: false}.

@app.post("/auth")
def auth_endpoint(payload: AuthRequest):
    email = payload.email.strip().lower()
    name = payload.name.strip() if payload.name else None
    result = get_or_create_user(name, email)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail={"exists": False})
    return result["user"]


# --- POST /chat ---
# Recibe el mensaje del usuario, selecciona el agente según la materia,
# mantiene el historial de la sesión y retorna la respuesta del modelo.

@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest, req: Request):
    try:
        logger.info(f'=== ENDPOINT /chat ===')
        logger.info(f'Materia: {request.materia}')
        logger.info(f'Session: {request.session_id}')

        # Validar inputs
        if len(request.message) > 500:
            raise HTTPException(status_code=400, detail="El mensaje no puede superar los 500 caracteres.")
        if len(request.session_id) > 64:
            raise HTTPException(status_code=400, detail="session_id inválido.")
        if request.device_fp and len(request.device_fp) > 128:
            raise HTTPException(status_code=400, detail="device_fp inválido.")
        if request.user_email and len(request.user_email) > 100:
            raise HTTPException(status_code=400, detail="email inválido.")

        # Verificar límite de tokens si viene user_email
        if request.user_email and not check_token_limit(request.user_email):
            raise HTTPException(status_code=429, detail="TOKEN_LIMIT_EXCEEDED")

        # Verificar rate limit (15 mensajes / 24hs).
        # Un solo identificador por orden de prioridad: email > device_fp > IP.
        # Así la WiFi de la universidad nunca bloquea a múltiples alumnos.
        ip_identifier = req.client.host
        email_identifier = request.user_email.strip().lower() if request.user_email else None
        fp_identifier = f"fp:{request.device_fp.strip()}" if request.device_fp else None

        if email_identifier:
            rl_identifier = email_identifier
        elif fp_identifier:
            rl_identifier = fp_identifier
        else:
            rl_identifier = ip_identifier

        rl_check = check_rate_limit(rl_identifier)
        if not rl_check["allowed"]:
            hours_left = round(rl_check["resets_in_seconds"] / 3600, 1)
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "RATE_LIMITED",
                    "remaining": 0,
                    "resets_in": rl_check["resets_in_seconds"],
                    "message": f"Alcanzaste el límite de 15 consultas. Se renueva en {hours_left} horas.",
                },
            )

        # Agregar el mensaje del usuario al historial de la sesión
        append_message(request.session_id, "user", request.message)

        # Obtener el historial completo para enviarlo al agente
        historial = get_messages(request.session_id)

        logger.info(f'Historial: {len(historial)} mensajes')

        # Seleccionar el agente según la materia indicada
        materia = request.materia.lower()
        if materia == "algebra":
            logger.info('Llamando a algebra_chat...')
            respuesta = algebra_chat(historial, session_id=request.session_id)
        elif materia == "calculo":
            logger.info('Llamando a calculo_chat...')
            respuesta = calculo_chat(historial, session_id=request.session_id)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Materia '{request.materia}' no reconocida. Opciones válidas: 'algebra', 'calculo'."
            )

        logger.info(f'Respuesta recibida: {len(respuesta)} chars')

        # Guardar la respuesta del asistente en el historial
        append_message(request.session_id, "assistant", respuesta)

        # Actualizar tokens usados (aproximado por longitud de respuesta)
        if request.user_email:
            add_tokens_used(request.user_email, len(respuesta))

        # Incrementar solo el identificador que se usó para verificar
        increment_rate_limit(rl_identifier)

        # Guardar historial de chat
        if request.user_email:
            try:
                save_chat_message(request.user_email, request.session_id, "user", request.message)
                save_chat_message(request.user_email, request.session_id, "assistant", respuesta)
            except Exception:
                pass

        return ChatResponse(response=respuesta, session_id=request.session_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'ERROR EN ENDPOINT: {type(e).__name__}')
        logger.error(f'Mensaje: {str(e)}')
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")


# --- POST /reset ---
# Limpia el historial de conversación de una sesión específica.

@app.post("/reset")
def reset_session(payload: dict):
    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(status_code=422, detail="Se requiere 'session_id'.")

    clear_session(session_id)
    return {"message": "Sesión reiniciada"}


# --- Admin helpers ---

def _require_admin(request: Request) -> str:
    email = request.headers.get("X-Admin-Email", "").strip().lower()
    pin = request.headers.get("X-Admin-Pin", "")
    admin_pin = os.getenv("ADMIN_PIN", "")
    if not email or not pin or pin != admin_pin or not is_admin_or_super(email):
        raise HTTPException(status_code=403, detail="Forbidden")
    return email


# --- POST /admin/verify ---

@app.post("/admin/verify")
def admin_verify(payload: AdminVerifyRequest):
    admin_pin = os.getenv("ADMIN_PIN", "")
    if payload.pin != admin_pin:
        return {"access": False, "reason": "pin"}
    email = payload.email.strip().lower()
    if not is_admin_or_super(email):
        return {"access": False, "reason": "role"}
    return {"access": True, "is_superadmin": is_superadmin(email)}


# --- GET /admin/check-access ---

@app.get("/admin/check-access")
def admin_check_access(request: Request):
    email = request.headers.get("X-Admin-Email", "").strip().lower()
    pin = request.headers.get("X-Admin-Pin", "")
    admin_pin = os.getenv("ADMIN_PIN", "")
    # Requiere PIN para no exponer qué emails son admin
    if not email or not pin or pin != admin_pin:
        return {"is_admin": False, "is_superadmin": False, "email": ""}
    _is_super = is_superadmin(email)
    _is_admin = is_admin_or_super(email)
    return {"is_admin": _is_admin, "is_superadmin": _is_super, "email": email}


# --- POST /admin/set-role ---

@app.post("/admin/set-role")
def admin_set_role(payload: SetRoleRequest, request: Request):
    caller = _require_admin(request)
    if not is_superadmin(caller):
        raise HTTPException(status_code=403, detail="Forbidden")
    if payload.role not in ("user", "admin"):
        raise HTTPException(status_code=422, detail="Rol inválido. Opciones: 'user', 'admin'.")
    target = get_user_by_email(payload.target_email.strip().lower())
    if not target:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    set_user_role(payload.target_email.strip().lower(), payload.role)
    return {"ok": True, "email": payload.target_email.strip().lower(), "role": payload.role}


# --- GET /admin/stats ---

@app.get("/admin/stats")
def admin_stats(request: Request):
    _require_admin(request)
    return get_stats()


# --- GET /admin/interactions ---

@app.get("/admin/interactions")
def admin_interactions(request: Request):
    _require_admin(request)
    return get_recent_interactions()


# --- GET /admin/users ---

@app.get("/admin/users")
def admin_users(request: Request):
    _require_admin(request)
    return get_all_users()


# --- POST /feedback ---

@app.post("/feedback")
def feedback_endpoint(payload: FeedbackRequest):
    if not 1 <= payload.rating <= 5:
        raise HTTPException(status_code=422, detail="El rating debe ser entre 1 y 5.")
    if payload.message and len(payload.message) > 1000:
        raise HTTPException(status_code=422, detail="El mensaje no puede superar los 1000 caracteres.")
    save_feedback(payload.user_email, payload.rating, payload.message)
    return {"ok": True}


# --- GET /admin/feedback ---

@app.get("/admin/feedback")
def admin_feedback(request: Request):
    _require_admin(request)
    return {"stats": get_feedback_stats(), "recent": get_recent_feedback()}


# --- POST /report-error ---

@app.post("/report-error")
def report_error(payload: ErrorReportRequest):
    desc = (payload.description or "").strip()
    if not desc:
        raise HTTPException(status_code=422, detail="La descripción no puede estar vacía.")
    if len(desc) > 500:
        raise HTTPException(status_code=422, detail="La descripción no puede superar los 500 caracteres.")
    result = save_error_report(payload.user_email or None, desc, payload.page or "chat")
    return {"ok": True, "id": result["id"]}


# --- GET /admin/reports ---

@app.get("/admin/reports")
def admin_reports(request: Request):
    _require_admin(request)
    return get_error_reports()


# --- POST /admin/reports/{id}/resolve ---

@app.post("/admin/reports/{report_id}/resolve")
def admin_resolve_report(report_id: int, request: Request):
    _require_admin(request)
    update_report_status(report_id, "resolved")
    return {"ok": True}


# --- GET /sessions/{session_id} ---
# Retorna el historial completo de mensajes de una sesión.

@app.get("/sessions/{session_id}")
def get_session_history(session_id: str):
    try:
        historial = get_messages(session_id)
        return {"session_id": session_id, "messages": historial}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener la sesión: {str(e)}")


# --- GET /history/{email} ---

@app.get("/history/{email}")
def user_sessions(email: str, request: Request):
    # Verificar que el solicitante sea el dueño del historial
    requesting_email = request.headers.get("X-User-Email", "").strip().lower()
    email_clean = email.strip().lower()
    if not requesting_email or requesting_email != email_clean:
        raise HTTPException(status_code=403, detail="Forbidden")
    return get_user_sessions(email_clean)


# --- GET /history/{email}/{session_id} ---

@app.get("/history/{email}/{session_id}")
def session_detail(email: str, session_id: str, request: Request):
    requesting_email = request.headers.get("X-User-Email", "").strip().lower()
    if not requesting_email or requesting_email != email.strip().lower():
        raise HTTPException(status_code=403, detail="Forbidden")
    return get_session_messages(session_id)


# --- GET /rate-limit ---

@app.get("/rate-limit")
def rate_limit_check(identifier: str):
    return check_rate_limit(identifier.strip().lower())


# --- POST /debug/fill-rate-limit ---

class FillRateLimitRequest(BaseModel):
    identifier: str
    count: int

@app.post("/debug/fill-rate-limit")
def debug_fill_rate_limit(payload: FillRateLimitRequest):
    identifier = payload.identifier.strip().lower()
    count = min(payload.count, 50)
    for _ in range(count):
        increment_rate_limit(identifier)
    return check_rate_limit(identifier)


# --- POST /payment/create-link ---

PLAN_QUANTITIES = {'basico': 15, 'estudiante': 60, 'intensivo': 200, 'apoyo': 60}

class PaymentLinkRequest(BaseModel):
    email: str
    plan: str = "apoyo"

@app.post("/payment/create-link")
def payment_create_link(payload: PaymentLinkRequest):
    email = payload.email.strip().lower()
    if not email:
        raise HTTPException(status_code=422, detail="Se requiere email.")
    plan = payload.plan if payload.plan in PLAN_QUANTITIES else "apoyo"
    try:
        url = create_payment_link(email, plan)
        return {"url": url}
    except ValueError as e:
        logger.error(f"Error de configuración en pago: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Error creando link de pago: {e}")
        raise HTTPException(status_code=500, detail="No se pudo generar el link de pago.")


# --- POST /payment/webhook ---

@app.post("/payment/webhook")
async def payment_webhook(req: Request):
    try:
        body = await req.json()
    except Exception:
        return {"ok": False}

    if body.get("type") != "payment":
        return {"ok": True}

    payment_id = body.get("data", {}).get("id")
    if not payment_id:
        return {"ok": True}

    try:
        from utils.payments import create_payment_link as _  # ensure module loaded
        import mercadopago, os
        sdk = mercadopago.SDK(os.getenv("MP_ACCESS_TOKEN", ""))
        result = sdk.payment().get(payment_id)
        payment = result.get("response", {})
        if payment.get("status") == "approved":
            ref = payment.get("external_reference", "").strip()
            if "|" in ref:
                plan, email = ref.split("|", 1)
                email = email.strip().lower()
            else:
                plan, email = "apoyo", ref.strip().lower()
            qty = PLAN_QUANTITIES.get(plan, 25)
            if email:
                grant_extra_messages(email, qty)
                logger.info(f"Pago aprobado: {qty} consultas extra otorgadas a {email} (plan: {plan})")
    except Exception as e:
        logger.error(f"Error procesando webhook de pago: {e}")

    return {"ok": True}


# --- GET /payment/status ---

@app.get("/payment/status")
def payment_status(email: str):
    return get_user_payment_status(email.strip().lower())
