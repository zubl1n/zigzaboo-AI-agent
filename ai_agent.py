import ssl
from fastapi import FastAPI, HTTPException
import requests

# Intentar importar openai, manejar el error si no está disponible
try:
    import openai
except ModuleNotFoundError:
    openai = None

# Asegurar que el módulo SSL está correctamente configurado
try:
    ssl.create_default_context()
except AttributeError:
    raise ImportError("El módulo SSL no está disponible en tu entorno de Python. Asegúrate de que Python está compilado con soporte para SSL.")

app = FastAPI()

# Configuración de claves API
WHATSAPP_API_URL = "https://graph.facebook.com/v17.0/YOUR_PHONE_NUMBER_ID/messages"
WHATSAPP_ACCESS_TOKEN = "YOUR_WHATSAPP_ACCESS_TOKEN"
WOOCOMMERCE_API_URL = "https://YOUR_STORE_URL/wp-json/wc/v3/"
WOOCOMMERCE_KEY = "YOUR_WOOCOMMERCE_KEY"
WOOCOMMERCE_SECRET = "YOUR_WOOCOMMERCE_SECRET"
OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"

if openai:
    openai.api_key = OPENAI_API_KEY

@app.get("/status")
def status():
    return {"message": "AI Agent is running"}

@app.post("/whatsapp-webhook")
def whatsapp_webhook(data: dict):
    try:
        message = data.get("messages", [])[0].get("text", "")
        sender = data.get("messages", [])[0].get("from", "")
        
        if detect_recommendation_request(message):
            response_text = recommend_product_based_on_history(sender)
        else:
            response_text = generate_ai_response(message)
        
        send_whatsapp_message(sender, response_text)
        
        return {"status": "Message processed"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/order-status/{order_id}")
def check_order_status(order_id: str):
    response = requests.get(
        f"{WOOCOMMERCE_API_URL}orders/{order_id}",
        auth=(WOOCOMMERCE_KEY, WOOCOMMERCE_SECRET),
        verify=True
    )
    if response.status_code == 200:
        order_data = response.json()
        return {"status": order_data.get("status", "Unknown"), "tracking": order_data.get("tracking", "No tracking info available")}
    else:
        raise HTTPException(status_code=404, detail="Order not found")


def generate_ai_response(user_message: str) -> str:
    if not openai:
        return "Error: El módulo OpenAI no está disponible."
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": user_message}]
    )
    return response["choices"][0]["message"]["content"].strip()


def detect_recommendation_request(message: str) -> bool:
    keywords = ["recomienda", "sugerir", "quiero comprar", "qué me recomiendas", "qué producto es bueno", "qué opción es mejor", "mejor producto"]
    return any(keyword in message.lower() for keyword in keywords)


def get_purchase_history(phone_number: str):
    response = requests.get(
        f"{WOOCOMMERCE_API_URL}orders?search={phone_number}",
        auth=(WOOCOMMERCE_KEY, WOOCOMMERCE_SECRET),
        verify=True
    )
    if response.status_code == 200:
        orders = response.json()
        purchased_products = []
        for order in orders:
            for item in order.get("line_items", []):
                purchased_products.append(item["name"])
        return purchased_products
    return []


def recommend_product_based_on_history(phone_number: str) -> str:
    purchase_history = get_purchase_history(phone_number)
    
    if not purchase_history:
        return "No encontré compras anteriores. Aquí tienes recomendaciones generales: " + recommend_product("sugerencias generales")
    
    query = ", ".join(purchase_history)
    response = requests.get(
        f"{WOOCOMMERCE_API_URL}products?search={query}&orderby=popularity&per_page=3",
        auth=(WOOCOMMERCE_KEY, WOOCOMMERCE_SECRET),
        verify=True
    )
    if response.status_code == 200:
        products = response.json()
        if products:
            recommendations = []
            for p in products:
                image_url = p['images'][0]['src'] if 'images' in p and p['images'] else "No disponible"
                availability = "✅ En stock" if p.get('stock_status', '') == "instock" else "❌ Agotado"
                description = p.get('short_description', 'No hay descripción disponible.')
                recommendations.append(
                    f"✨ *{p['name']}* \n💲 Precio: {p['price']} {p['currency']} \n📄 {description}\n{availability}\n🔗 [Ver producto]({p['permalink']}) \n🖼️ Imagen: {image_url}"
                )
            return "🌟 *Aquí tienes algunas opciones recomendadas basadas en tu historial de compras:*\n\n" + "\n\n".join(recommendations)
        else:
            return "⚠️ No encontré productos similares a tus compras anteriores."
    else:
        return "❌ No pude obtener recomendaciones en este momento."


def send_whatsapp_message(phone_number: str, message: str):
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "text": {"body": message},
        "preview_url": True
    }
    response = requests.post(WHATSAPP_API_URL, headers=headers, json=payload, verify=True)
    return response.json()
