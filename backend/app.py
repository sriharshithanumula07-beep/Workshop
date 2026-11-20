import os
from flask import Flask, request, jsonify
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"}), 200


# CORS enabled manually (no flask-cors dependency)
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response


@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        return "", 204



# Supabase connection
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY")


if not SUPABASE_URL or not SUPABASE_PUBLISHABLE_KEY:
    raise RuntimeError("Please set SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY in your .env file")


supabase: Client = create_client(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY)


# --------------------------------------------------
# GET /api/events - Browse events
# --------------------------------------------------
@app.route("/api/events", methods=["GET"])
def get_events():
    try:
        response = supabase.table("events").select("*").execute()
        return jsonify({"success": True, "events": response.data}), 200
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500


# --------------------------------------------------
# GET /api/events/<event_id> - Event details
# --------------------------------------------------
@app.route("/api/events/<event_id>", methods=["GET"])
def get_event(event_id):
    try:
        response = (
            supabase.table("events")
            .select("*")
            .eq("id", event_id)
            .execute()
        )
        if not response.data:
            return jsonify({"success": False, "message": "Event not found"}), 404
        return jsonify({"success": True, "event": response.data[0]}), 200
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500


# --------------------------------------------------
# POST /api/registrations - Register for an event
# JSON body: {"user_id": "UUID", "event_id": "UUID"}
# --------------------------------------------------
@app.route("/api/registrations", methods=["POST"])
def create_registration():
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"success": False, "message": "A JSON body is required"}), 400

        user_id = data.get("user_id")
        event_id = data.get("event_id")
        if not user_id or not event_id:
            return jsonify({"success": False, "message": "user_id and event_id are required"}), 400

        # Confirm the event exists
        event_response = (
            supabase.table("events")
            .select("*")
            .eq("id", event_id)
            .execute()
        )
        if not event_response.data:
            return jsonify({"success": False, "message": "Event not found"}), 404
        event = event_response.data[0]

        existing_registration = (
            supabase.table("registrations")
            .select("id")
            .eq("user_id", user_id)
            .eq("event_id", event_id)
            .execute()
        )
        if existing_registration.data:
            return jsonify({"success": False, "message": "Already registered for this event"}), 409

        if event.get("capacity") is not None:
            registrations_response = (
                supabase.table("registrations")
                .select("id", count="exact")                    
                .eq("event_id", event_id)
                .execute()
            )
            registration_count = registrations_response.count
            if registration_count is None:
                registration_count = len(registrations_response.data or [])
            if registration_count >= event["capacity"]:
                return jsonify({"success": False, "message": "Event is full"}), 409

        response = (
            supabase.table("registrations")
            .insert({"user_id": user_id, "event_id": event_id})
            .execute()
        )
        return jsonify({"success": True, "registration": response.data[0]}), 201
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500


# --------------------------------------------------
# GET /api/me/registrations - Registrations for a user
# Requires user_id as a query parameter because this API has no authentication.
# --------------------------------------------------
@app.route("/api/me/registrations", methods=["GET"])
def get_my_registrations():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "user_id query parameter is required"}), 400

    try:
        response = (
            supabase.table("registrations")
            .select("*, events(*)")
            .eq("user_id", user_id)
            .execute()
        )
        return jsonify({"success": True, "registrations": response.data}), 200
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500


# --------------------------------------------------
# GET /api/events/<event_id>/registrations - Event attendees
# Public because this API intentionally has no authentication or authorization.
# --------------------------------------------------
@app.route("/api/events/<event_id>/registrations", methods=["GET"])
def get_event_registrations(event_id):
    try:
        event_response = (
            supabase.table("events")
            .select("id")
            .eq("id", event_id)
            .execute()
        )
        if not event_response.data:
            return jsonify({"success": False, "message": "Event not found"}), 404

        response = (
            supabase.table("registrations")
            .select("*, users(*)")
            .eq("event_id", event_id)
            .execute()
        )
        return jsonify({"success": True, "registrations": response.data}), 200
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500
        